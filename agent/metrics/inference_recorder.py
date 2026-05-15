from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class InferenceRecorder:
    def __init__(self, db_path: str | Path = "data/inference_replay.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
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
                    ground_truth_status TEXT,
                    retrain_flag INTEGER DEFAULT 0
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_inference_records_correlation_id ON inference_records(correlation_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_inference_records_recorded_at ON inference_records(recorded_at)")
            self._conn.commit()

    def record(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO inference_records (
                    record_id, correlation_id, input_json, output_json, market_state_json,
                    model_version, model_checksum, tee_mode, inference_latency_ms, recorded_at,
                    ground_truth_profit_usdc, ground_truth_status, retrain_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("record_id"),
                    payload.get("correlation_id"),
                    payload.get("input_json"),
                    payload.get("output_json"),
                    payload.get("market_state_json"),
                    payload.get("model_version"),
                    payload.get("model_checksum"),
                    payload.get("tee_mode"),
                    payload.get("inference_latency_ms"),
                    payload.get("recorded_at"),
                    payload.get("ground_truth_profit_usdc"),
                    payload.get("ground_truth_status"),
                    int(payload.get("retrain_flag", 0)),
                ),
            )
            self._conn.commit()

    def update_ground_truth(self, opportunity_id: str, realized_profit_usdc: Any, status: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE inference_records
                SET ground_truth_profit_usdc = ?, ground_truth_status = ?
                WHERE correlation_id = ? OR record_id = ?
                """,
                (realized_profit_usdc, status, opportunity_id, opportunity_id),
            )
            self._conn.commit()

    def flag_for_retraining(self, opportunity_id: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE inference_records
                SET retrain_flag = 1
                WHERE correlation_id = ? OR record_id = ?
                """,
                (opportunity_id, opportunity_id),
            )
            self._conn.commit()
