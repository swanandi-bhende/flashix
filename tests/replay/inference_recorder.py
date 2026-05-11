from __future__ import annotations

import dataclasses
from dataclasses import asdict
from decimal import Decimal
import json
import logging
from pathlib import Path
import queue
import sqlite3
import threading
import time
from typing import Any
from uuid import uuid4

from compute.arbitrage_analyzer import InferenceInput, InferenceOutput

from .inference_replay import MarketConditions, ReplayJSONEncoder, coerce_inference_input, coerce_inference_output, now_ts


_logger = logging.getLogger(__name__)


class InferenceRecorder:
    def __init__(self, db_path: str | Path = "data/inference_replay.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema(self._conn)
        self._conn.commit()
        self._writer = threading.Thread(target=self._writer_loop, name="inference-replay-writer", daemon=True)
        self._writer.start()

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inference_records (
                record_id TEXT PRIMARY KEY,
                correlation_id TEXT,
                input_json TEXT,
                output_json TEXT,
                market_state_json TEXT,
                model_version TEXT,
                model_checksum TEXT,
                tee_mode TEXT,
                inference_latency_ms REAL,
                recorded_at INTEGER,
                ground_truth_profit_usdc REAL,
                ground_truth_status TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_correlation_id ON inference_records(correlation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recorded_at ON inference_records(recorded_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decision ON inference_records(json_extract(output_json, '$.decision'))"
        )

    def _default_metadata(self) -> tuple[str, str]:
        try:
            from compute.model_loader import MODEL_SINGLETON

            metadata = MODEL_SINGLETON[1]
            return str(getattr(metadata, "version", "unknown")), str(getattr(metadata, "sha256_checksum", ""))
        except Exception:
            return "unknown", ""

    def _serialize(self, obj: Any) -> str:
        return json.dumps(obj, cls=ReplayJSONEncoder, sort_keys=True)

    def _writer_loop(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                action, payload = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                if action == "record":
                    with self._lock:
                        self._conn.execute(
                            """
                            INSERT OR REPLACE INTO inference_records (
                                record_id, correlation_id, input_json, output_json, market_state_json,
                                model_version, model_checksum, tee_mode, inference_latency_ms, recorded_at,
                                ground_truth_profit_usdc, ground_truth_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                payload["record_id"],
                                payload["correlation_id"],
                                payload["input_json"],
                                payload["output_json"],
                                payload["market_state_json"],
                                payload["model_version"],
                                payload["model_checksum"],
                                payload["tee_mode"],
                                payload["inference_latency_ms"],
                                payload["recorded_at"],
                                payload.get("ground_truth_profit_usdc"),
                                payload.get("ground_truth_status"),
                            ),
                        )
                        self._conn.commit()
                elif action == "update_ground_truth":
                    with self._lock:
                        self._conn.execute(
                            """
                            UPDATE inference_records
                            SET ground_truth_profit_usdc = ?, ground_truth_status = ?
                            WHERE correlation_id = ?
                            """,
                            (
                                payload["ground_truth_profit_usdc"],
                                payload["ground_truth_status"],
                                payload["correlation_id"],
                            ),
                        )
                        self._conn.commit()
            finally:
                self._queue.task_done()

    def record(
        self,
        input: InferenceInput,
        output: InferenceOutput,
        market_state: MarketConditions,
        latency_ms: float,
        correlation_id: str | None = None,
    ) -> None:
        record_id = str(uuid4())
        correlation_id = correlation_id or str(getattr(input, "opportunity_id", record_id))
        model_version, model_checksum = self._default_metadata()
        tee_mode = str(getattr(output, "tee_signature", "LOCAL"))
        payload = {
            "record_id": record_id,
            "correlation_id": correlation_id,
            "input_json": self._serialize(asdict(coerce_inference_input(input))),
            "output_json": self._serialize(asdict(coerce_inference_output(output))),
            "market_state_json": self._serialize(asdict(market_state)),
            "model_version": model_version,
            "model_checksum": model_checksum,
            "tee_mode": tee_mode,
            "inference_latency_ms": float(latency_ms),
            "recorded_at": now_ts(),
            "ground_truth_profit_usdc": None,
            "ground_truth_status": None,
        }
        try:
            self._queue.put_nowait(("record", payload))
        except queue.Full:
            with self._lock:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO inference_records (
                        record_id, correlation_id, input_json, output_json, market_state_json,
                        model_version, model_checksum, tee_mode, inference_latency_ms, recorded_at,
                        ground_truth_profit_usdc, ground_truth_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["record_id"],
                        payload["correlation_id"],
                        payload["input_json"],
                        payload["output_json"],
                        payload["market_state_json"],
                        payload["model_version"],
                        payload["model_checksum"],
                        payload["tee_mode"],
                        payload["inference_latency_ms"],
                        payload["recorded_at"],
                        payload["ground_truth_profit_usdc"],
                        payload["ground_truth_status"],
                    ),
                )
                self._conn.commit()

    def update_ground_truth(self, correlation_id: str, realized_profit_usdc: Decimal, status: str) -> None:
        payload = {
            "correlation_id": correlation_id,
            "ground_truth_profit_usdc": float(realized_profit_usdc),
            "ground_truth_status": status,
        }
        try:
            self._queue.put_nowait(("update_ground_truth", payload))
        except queue.Full:
            with self._lock:
                self._conn.execute(
                    """
                    UPDATE inference_records
                    SET ground_truth_profit_usdc = ?, ground_truth_status = ?
                    WHERE correlation_id = ?
                    """,
                    (
                        payload["ground_truth_profit_usdc"],
                        payload["ground_truth_status"],
                        payload["correlation_id"],
                    ),
                )
                self._conn.commit()

    def flag_for_retraining(self, correlation_id: str) -> None:
        self.update_ground_truth(correlation_id, Decimal("0"), "UNPROFITABLE")
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM inference_records WHERE correlation_id = ?",
                (correlation_id,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO inference_records (
                        record_id, correlation_id, input_json, output_json, market_state_json,
                        model_version, model_checksum, tee_mode, inference_latency_ms, recorded_at,
                        ground_truth_profit_usdc, ground_truth_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        correlation_id,
                        correlation_id,
                        None,
                        None,
                        None,
                        "unknown",
                        "",
                        "REPLAY",
                        0.0,
                        int(__import__("time").time() * 1000),
                        0.0,
                        "UNPROFITABLE",
                    ),
                )
                self._conn.commit()

    def flush(self) -> None:
        self._queue.join()

    def close(self) -> None:
        self._stop_event.set()
        self.flush()
        if self._writer.is_alive():
            self._writer.join(timeout=2)
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "InferenceRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
