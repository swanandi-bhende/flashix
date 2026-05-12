from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

from agent.metrics import Alert, Metric, MetricName, metric_snapshot_key


class MetricsStore:
    def __init__(self, db_path: str | Path = "data/metrics.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    value REAL,
                    labels_json TEXT,
                    component TEXT,
                    timestamp_ms INTEGER
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, timestamp_ms)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_component_ts ON metrics(component, timestamp_ms)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recent ON metrics(timestamp_ms)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    severity TEXT,
                    metric_name TEXT,
                    current_value REAL,
                    threshold_value REAL,
                    message TEXT,
                    triggered_at INTEGER,
                    resolved_at INTEGER,
                    acknowledged INTEGER
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(resolved_at, acknowledged, severity)")

    def insert_batch(self, metrics: list[Metric]) -> None:
        if not metrics:
            return
        rows = [
            (
                f"{metric_snapshot_key(metric)}:{metric.timestamp_ms}:{metric.component}",
                metric.name.value,
                metric.type.value,
                float(metric.value),
                json.dumps(metric.labels, sort_keys=True),
                metric.component,
                int(metric.timestamp_ms),
            )
            for metric in metrics
        ]
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN")
            conn.executemany(
                """
                INSERT OR REPLACE INTO metrics (
                    metric_id, name, type, value, labels_json, component, timestamp_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

    def upsert_alert(self, alert: Alert) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts (
                    alert_id, severity, metric_name, current_value, threshold_value,
                    message, triggered_at, resolved_at, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.alert_id,
                    alert.severity.value,
                    alert.metric_name.value,
                    float(alert.current_value),
                    float(alert.threshold_value),
                    alert.message,
                    int(alert.triggered_at),
                    alert.resolved_at,
                    1 if alert.acknowledged else 0,
                ),
            )
            conn.commit()

    def list_active_alerts(self) -> list[Alert]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM alerts
                WHERE resolved_at IS NULL
                ORDER BY CASE severity WHEN 'EMERGENCY' THEN 4 WHEN 'CRITICAL' THEN 3 WHEN 'WARNING' THEN 2 ELSE 1 END DESC,
                         triggered_at DESC
                """
            ).fetchall()
        from agent.metrics import AlertSeverity

        return [
            Alert(
                alert_id=row["alert_id"],
                severity=AlertSeverity(row["severity"]),
                metric_name=MetricName(row["metric_name"]),
                current_value=float(row["current_value"]),
                threshold_value=float(row["threshold_value"]),
                message=row["message"],
                triggered_at=int(row["triggered_at"]),
                resolved_at=int(row["resolved_at"]) if row["resolved_at"] is not None else None,
                acknowledged=bool(row["acknowledged"]),
            )
            for row in rows
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?", (alert_id,))
            conn.commit()
            return cur.rowcount > 0

    def query_timeseries(self, metric_name: MetricName, from_ms: int, to_ms: int, resolution_ms: int = 5000) -> list[tuple[int, float]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT CAST(ROUND(timestamp_ms * 1.0 / ?) AS INTEGER) * ? AS bucket_ts,
                       AVG(value) AS bucket_value
                FROM metrics
                WHERE name = ? AND timestamp_ms BETWEEN ? AND ?
                GROUP BY bucket_ts
                ORDER BY bucket_ts ASC
                """,
                (resolution_ms, resolution_ms, metric_name.value, from_ms, to_ms),
            ).fetchall()
        return [(int(row["bucket_ts"]), float(row["bucket_value"])) for row in rows if row["bucket_value"] is not None]

    def downsample_old_data(self) -> None:
        now_ms = int(time.time() * 1000)
        minute_cutoff = now_ms - 60 * 60 * 1000
        hour_cutoff = now_ms - 24 * 60 * 60 * 1000
        with self._lock, self._connect() as conn:
            old_rows = conn.execute(
                "SELECT * FROM metrics WHERE timestamp_ms < ? ORDER BY timestamp_ms ASC",
                (minute_cutoff,),
            ).fetchall()
            if not old_rows:
                return
            conn.execute("BEGIN")
            for bucket_ms, bucket_rows in self._bucket_rows(old_rows, resolution_ms=300_000).items():
                if bucket_ms < hour_cutoff:
                    # Preserve minute history as hourly rollups once the data is older than 24h.
                    hour_bucket = int(round(bucket_ms / 3_600_000.0)) * 3_600_000
                    self._write_rollup(conn, hour_bucket, bucket_rows, bucket_label="hour")
                else:
                    self._write_rollup(conn, bucket_ms, bucket_rows, bucket_label="minute")
            metric_ids = [row["metric_id"] for row in old_rows]
            conn.executemany("DELETE FROM metrics WHERE metric_id = ?", [(metric_id,) for metric_id in metric_ids])
            conn.commit()

    def _bucket_rows(self, rows: Iterable[sqlite3.Row], resolution_ms: int) -> dict[int, list[sqlite3.Row]]:
        buckets: dict[int, list[sqlite3.Row]] = {}
        for row in rows:
            bucket_ts = int(round(int(row["timestamp_ms"]) / resolution_ms)) * resolution_ms
            buckets.setdefault(bucket_ts, []).append(row)
        return buckets

    def _write_rollup(self, conn: sqlite3.Connection, bucket_ts: int, rows: list[sqlite3.Row], bucket_label: str) -> None:
        by_metric: dict[tuple[str, str, str], list[float]] = {}
        for row in rows:
            key = (row["name"], row["type"], row["component"])
            by_metric.setdefault(key, []).append(float(row["value"]))
        for (name, metric_type, component), values in by_metric.items():
            min_value = min(values)
            max_value = max(values)
            avg_value = sum(values) / len(values)
            conn.execute(
                """
                INSERT OR REPLACE INTO metrics (
                    metric_id, name, type, value, labels_json, component, timestamp_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"rollup:{bucket_label}:{name}:{bucket_ts}:{component}",
                    name,
                    metric_type,
                    float(avg_value),
                    json.dumps(
                        {
                            "aggregate": "avg",
                            "window": bucket_label,
                            "min": min_value,
                            "max": max_value,
                            "count": len(values),
                            "avg": avg_value,
                        },
                        sort_keys=True,
                    ),
                    component,
                    bucket_ts,
                ),
            )

    def prune_old_data(self, max_age_days: int = 7) -> None:
        cutoff = int(time.time() * 1000) - max_age_days * 24 * 60 * 60 * 1000
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM metrics WHERE timestamp_ms < ?", (cutoff,))
            conn.execute("DELETE FROM alerts WHERE resolved_at IS NOT NULL AND resolved_at < ?", (cutoff,))
            conn.commit()
