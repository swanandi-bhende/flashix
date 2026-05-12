from __future__ import annotations

import logging
import statistics
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from redis import Redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TuningRecommendation:
    stage: str
    recommendation: str
    reason: str


@dataclass(frozen=True)
class BottleneckReport:
    stage_p50_ms: dict[str, float]
    stage_p95_ms: dict[str, float]
    stage_p99_ms: dict[str, float]
    bottleneck_stage: str
    bottleneck_p95_ms: float
    bottleneck_pct_of_total: float
    samples: int


class BottleneckProfiler:
    STAGES = [
        "mempool_to_filter",
        "filter_to_inference",
        "inference_execution",
        "inference_to_agent",
        "agent_reasoning",
        "agent_to_execution",
        "execution_submission",
        "confirmation_wait",
        "settlement",
    ]

    def __init__(self, redis_client: Any | None = None, sqlite_path: str | Path = "data/trades.db", auto_start: bool = True) -> None:
        self.redis_client = redis_client or Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        self.sqlite_path = Path(sqlite_path)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if auto_start:
            self.start()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="bottleneck-profiler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                report = self.profile()
                recommendations = self.generate_recommendations(report)
                if recommendations:
                    logger.info("BOTTLENECK_RECOMMENDATION: %s", recommendations[0].recommendation)
            except Exception:
                logger.exception("BOTTLENECK_PROFILER_ERROR")
            self._stop_event.wait(300)

    def profile(self, lookback_n: int = 200) -> BottleneckReport:
        records = self._load_records(lookback_n)
        stage_samples: dict[str, list[float]] = {stage: [] for stage in self.STAGES}
        for record in records:
            timeline = record.get("stage_timeline") or []
            for entry in timeline:
                stage = str(entry.get("stage", "")).lower()
                if stage not in stage_samples:
                    continue
                entered = entry.get("entered_at_ms")
                exited = entry.get("exited_at_ms")
                if entered is None or exited is None:
                    continue
                duration = float(max(0, int(exited) - int(entered)))
                stage_samples[stage].append(duration)

        stage_p50 = {stage: self._percentile(values, 50) for stage, values in stage_samples.items()}
        stage_p95 = {stage: self._percentile(values, 95) for stage, values in stage_samples.items()}
        stage_p99 = {stage: self._percentile(values, 99) for stage, values in stage_samples.items()}
        bottleneck_stage = max(stage_p95, key=stage_p95.get, default="")
        bottleneck_p95 = stage_p95.get(bottleneck_stage, 0.0)
        total = sum(stage_p95.values()) or 1.0
        return BottleneckReport(
            stage_p50_ms=stage_p50,
            stage_p95_ms=stage_p95,
            stage_p99_ms=stage_p99,
            bottleneck_stage=bottleneck_stage,
            bottleneck_p95_ms=bottleneck_p95,
            bottleneck_pct_of_total=(bottleneck_p95 / total) * 100.0,
            samples=len(records),
        )

    def _load_records(self, lookback_n: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            keys = self.redis_client.keys("flashix:correlation:*")
            for key in keys[:lookback_n]:
                payload = self.redis_client.hgetall(key)
                if not payload:
                    continue
                timeline = payload.get("stage_timeline")
                if isinstance(timeline, str):
                    import json

                    try:
                        timeline = json.loads(timeline)
                    except Exception:
                        timeline = []
                records.append({"correlation_id": key.split(":")[-1], "stage_timeline": timeline or []})
        except Exception:
            logger.exception("REDIS_CORRELATION_LOAD_ERROR")

        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT payload FROM trade_records ORDER BY rowid DESC LIMIT ?", (lookback_n,)).fetchall()
            for row in rows:
                import json

                try:
                    payload = json.loads(row["payload"])
                except Exception:
                    continue
                timeline = payload.get("stage_timeline") or payload.get("payload", {}).get("stage_timeline") or []
                records.append({"correlation_id": payload.get("correlation_id", ""), "stage_timeline": timeline})
        except Exception:
            pass
        return records[:lookback_n]

    def generate_recommendations(self, report: BottleneckReport) -> list[TuningRecommendation]:
        recommendations: list[TuningRecommendation] = []
        inference_p95 = report.stage_p95_ms.get("inference_execution", 0.0)
        agent_reasoning_p95 = report.stage_p95_ms.get("agent_reasoning", 0.0)
        confirmation_wait_p95 = report.stage_p95_ms.get("confirmation_wait", 0.0)
        mempool_to_filter_p95 = report.stage_p95_ms.get("mempool_to_filter", 0.0)

        if inference_p95 > 2000:
            recommendations.append(
                TuningRecommendation(
                    stage="inference_execution",
                    recommendation="Increase InferenceWorker thread count from 2 to 3, or upgrade 0G Compute tier",
                    reason=f"p95 latency {inference_p95:.0f}ms is above target",
                )
            )
        if agent_reasoning_p95 > 20000:
            recommendations.append(
                TuningRecommendation(
                    stage="agent_reasoning",
                    recommendation="Reduce GEMINI_MAX_TOKENS from 2048 to 1024 or switch to gemini-1.5-flash-8b for faster reasoning",
                    reason=f"p95 latency {agent_reasoning_p95:.0f}ms is above target",
                )
            )
        if confirmation_wait_p95 > 15000:
            recommendations.append(
                TuningRecommendation(
                    stage="confirmation_wait",
                    recommendation="0G Chain block time is slow — consider increasing execution_timeout or using a faster RPC endpoint",
                    reason=f"p95 latency {confirmation_wait_p95:.0f}ms is above target",
                )
            )
        if mempool_to_filter_p95 > 200:
            recommendations.append(
                TuningRecommendation(
                    stage="mempool_to_filter",
                    recommendation="Filter engine CPU-bound — enable PyPy or move filtering to Rust via CFFI",
                    reason=f"p95 latency {mempool_to_filter_p95:.0f}ms is above target",
                )
            )
        return recommendations

    def _percentile(self, values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        values_sorted = sorted(values)
        index = int(round((percentile / 100.0) * (len(values_sorted) - 1)))
        index = max(0, min(index, len(values_sorted) - 1))
        return float(values_sorted[index])
