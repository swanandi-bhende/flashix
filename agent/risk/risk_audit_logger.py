"""Audit logger for circuit breaker events."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, request

from agent.risk_manager import BreakerAnalytics, BreakerType, CircuitBreakerEvent, CircuitBreakerState, RiskLevel, _enum_value


class RiskAuditLogger:
    def __init__(self, data_dir: str = "data", registry: Any = None, db_path: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.jsonl_path = self.data_dir / "circuit_breaker_events.jsonl"
        self.human_override_path = self.data_dir / "human_overrides.jsonl"
        self.db_path = Path(db_path) if db_path else self.data_dir / "circuit_breaker_events.db"
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    event_id TEXT PRIMARY KEY,
                    breaker_type TEXT NOT NULL,
                    state_before TEXT NOT NULL,
                    state_after TEXT NOT NULL,
                    trigger_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    opportunity_id TEXT,
                    triggered_at INTEGER NOT NULL,
                    auto_reset_at INTEGER,
                    resolved_at INTEGER,
                    resolution_method TEXT,
                    notes TEXT,
                    system_risk_level_at_trigger TEXT NOT NULL,
                    concurrent_positions_at_trigger INTEGER NOT NULL
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_breaker_type ON circuit_breaker_events(breaker_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggered_at ON circuit_breaker_events(triggered_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opportunity_id ON circuit_breaker_events(opportunity_id)")
            conn.commit()
        finally:
            conn.close()

    def _snapshot_context(self) -> tuple[RiskLevel, int]:
        if self.registry is None:
            return RiskLevel.GREEN, 0
        snapshot = self.registry.get_snapshot()
        return snapshot.risk_level, snapshot.concurrent_positions

    def record_event(self, event: CircuitBreakerEvent) -> None:
        snapshot_level, concurrent_positions = self._snapshot_context()
        payload = asdict(event)
        payload["breaker_type"] = event.breaker_type.value
        payload["state_before"] = event.state_before.value
        payload["state_after"] = event.state_after.value
        payload["system_risk_level_at_trigger"] = snapshot_level.value
        payload["concurrent_positions_at_trigger"] = concurrent_positions
        line = json.dumps(_enum_value(payload), separators=(",", ":")) + "\n"
        fd = os.open(self.jsonl_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

        conn = sqlite3.connect(self.db_path, timeout=1.0)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO circuit_breaker_events (
                    event_id, breaker_type, state_before, state_after, trigger_value,
                    threshold_value, opportunity_id, triggered_at, auto_reset_at,
                    resolved_at, resolution_method, notes,
                    system_risk_level_at_trigger, concurrent_positions_at_trigger
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.breaker_type.value,
                    event.state_before.value,
                    event.state_after.value,
                    event.trigger_value,
                    event.threshold_value,
                    event.opportunity_id,
                    event.triggered_at,
                    event.auto_reset_at,
                    event.resolved_at,
                    event.resolution_method,
                    event.notes,
                    snapshot_level.value,
                    concurrent_positions,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        if event.breaker_type in {BreakerType.DAILY_LOSS_CAP, BreakerType.HUMAN_OVERRIDE, BreakerType.POSITION_TIMEOUT}:
            webhook_url = os.getenv("OPS_WEBHOOK_URL", "").strip()
            if webhook_url:
                payload_bytes = json.dumps(
                    _enum_value(
                        {
                            "event": asdict(event),
                            "system_risk_level_at_trigger": snapshot_level.value,
                            "concurrent_positions_at_trigger": concurrent_positions,
                        }
                    )
                ).encode("utf-8")
                req = request.Request(webhook_url, data=payload_bytes, headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with request.urlopen(req, timeout=0.5):
                        pass
                except error.URLError:
                    pass

    def record_human_override(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        fd = os.open(self.human_override_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def get_breaker_analytics(self, hours: int = 24) -> BreakerAnalytics:
        cutoff = int(time.time()) - hours * 3600
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM circuit_breaker_events WHERE triggered_at >= ? ORDER BY triggered_at ASC",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        open_events = [row for row in rows if row["state_after"] == CircuitBreakerState.OPEN.value]
        events_by_type = Counter(BreakerType(row["breaker_type"]) for row in open_events)
        total_events = len(open_events)
        most_frequent = events_by_type.most_common(1)[0][0] if events_by_type else None

        duration_by_type: Dict[BreakerType, list[float]] = defaultdict(list)
        total_open_seconds = 0.0
        false_positive_resets = 0
        open_times: Dict[str, tuple[BreakerType, int]] = {}
        for row in rows:
            breaker = BreakerType(row["breaker_type"])
            if row["state_after"] == CircuitBreakerState.OPEN.value:
                open_times[row["event_id"]] = (breaker, row["triggered_at"])
            elif row["resolved_at"] is not None:
                duration = max(0, row["resolved_at"] - row["triggered_at"])
                duration_by_type[breaker].append(duration)
                total_open_seconds += duration
                if row["resolution_method"] in {"AUTO_RESET", "CONDITION_CLEARED"}:
                    false_positive_resets += 1

        avg_times = {breaker: (sum(values) / len(values) if values else 0.0) for breaker, values in duration_by_type.items()}
        total_seconds = max(1, hours * 3600)
        trading_uptime = max(0.0, (total_seconds - min(total_seconds, total_open_seconds)) / total_seconds * 100)
        false_positive_rate = false_positive_resets / total_events if total_events else 0.0

        return BreakerAnalytics(
            total_events=total_events,
            events_by_type=dict(events_by_type),
            most_frequent_breaker=most_frequent,
            avg_time_open_seconds_by_type=avg_times,
            false_positive_rate_estimate=false_positive_rate,
            trading_uptime_pct=trading_uptime,
        )
