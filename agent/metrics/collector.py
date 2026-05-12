from __future__ import annotations

import json
import logging
import math
import sqlite3
import statistics
import threading
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, Optional

from agent.market_data.freshness_monitor import FreshnessMonitor
from agent.market_data.window_store import MarketStateWindowStore
from agent.metrics import (
    ALERT_DAILY_PNL_WARN_USDC,
    ALERT_EXECUTION_SUCCESS_RATE_MIN,
    ALERT_GAS_PRICE_SPIKE_PCT,
    ALERT_QUEUE_DEPTH_MAX,
    DEFAULT_METRIC_COMPONENT,
    INITIAL_CAPITAL_USDC,
    METRICS_COLLECTION_INTERVAL_SECONDS,
    Metric,
    MetricName,
    MetricType,
    RISK_FREE_RATE_DAILY,
    metric_name_key,
    metric_snapshot_key,
)
from agent.pipeline.queue_manager import QueueManager
from agent.risk.position_watchdog import PositionWatchdog
from agent.risk.risk_registry import RiskRegistry
from agent.settlement.ledger import SettlementLedger
from tests.replay.inference_recorder import InferenceRecorder

logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(
        self,
        settlement_ledger: SettlementLedger,
        risk_registry: RiskRegistry,
        window_store: MarketStateWindowStore,
        queue_manager: QueueManager,
        inference_recorder: InferenceRecorder,
        position_watchdog: PositionWatchdog,
        freshness_monitor: FreshnessMonitor,
        metrics_store: Any | None = None,
        auto_start: bool = True,
    ) -> None:
        self.settlement_ledger = settlement_ledger
        self.risk_registry = risk_registry
        self.window_store = window_store
        self.queue_manager = queue_manager
        self.inference_recorder = inference_recorder
        self.position_watchdog = position_watchdog
        self.freshness_monitor = freshness_monitor
        self.metrics_store = metrics_store
        self.current_snapshot: dict[str, Metric] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if auto_start:
            self.start_background_collection()

    def start_background_collection(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._collection_loop, name="metrics-collector", daemon=True)
        self._thread.start()

    def stop_background_collection(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _collection_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self.collect_all()
                if self.metrics_store is not None:
                    self.metrics_store.insert_batch(snapshot)
            except Exception:
                logger.exception("METRICS_COLLECTION_ERROR")
            self._stop_event.wait(METRICS_COLLECTION_INTERVAL_SECONDS)

    def _connect_ledger(self) -> sqlite3.Connection:
        return self.settlement_ledger._connect()

    def _metric(self, name: MetricName, metric_type: MetricType, value: float, labels: Optional[dict[str, str]] = None, component: str = DEFAULT_METRIC_COMPONENT, timestamp_ms: Optional[int] = None) -> Metric:
        return Metric(
            name=name,
            type=metric_type,
            value=float(value),
            labels=dict(labels or {}),
            timestamp_ms=int(timestamp_ms or time.time() * 1000),
            component=component,
        )

    def _dedupe(self, metrics: Iterable[Metric]) -> list[Metric]:
        deduped: dict[str, Metric] = {}
        for metric in metrics:
            key = metric_snapshot_key(metric)
            current = deduped.get(key)
            if current is None or metric.timestamp_ms >= current.timestamp_ms:
                deduped[key] = metric
        return sorted(deduped.values(), key=lambda item: (item.name.value, item.timestamp_ms))

    def collect_execution_metrics(self) -> list[Metric]:
        cutoff_ms = int(time.time() * 1000) - 60 * 60 * 1000
        with self._connect_ledger() as conn:
            rows = conn.execute(
                """
                SELECT * FROM settlement_records
                WHERE settled_at >= ?
                ORDER BY settled_at ASC
                """,
                (cutoff_ms,),
            ).fetchall()

        total_detected = len(rows)
        confirmed_rows = [row for row in rows if row["receipt_status"] == "CONFIRMED"]
        reverted_rows = [row for row in rows if row["receipt_status"] == "REVERTED"]
        timeout_rows = [row for row in rows if row["receipt_status"] == "TIMEOUT"]
        denom = confirmed_rows + reverted_rows + timeout_rows
        success_rate = len(confirmed_rows) / len(denom) if denom else 0.0

        mempool_to_decision = [
            float(row["execution_submit_ms"] - row["first_seen_in_mempool_ms"])
            for row in confirmed_rows
            if row["execution_submit_ms"] is not None and row["first_seen_in_mempool_ms"] is not None
        ]
        decision_to_settlement = [
            float(row["total_execution_latency_ms"] - (row["execution_submit_ms"] - row["first_seen_in_mempool_ms"]))
            for row in confirmed_rows
            if row["total_execution_latency_ms"] is not None and row["execution_submit_ms"] is not None and row["first_seen_in_mempool_ms"] is not None
        ]
        end_to_end = [float(row["total_execution_latency_ms"]) for row in confirmed_rows if row["total_execution_latency_ms"] is not None]
        profits = [float(row["realized_profit_usdc"]) for row in confirmed_rows if row["realized_profit_usdc"] is not None]

        metrics = [
            self._metric(MetricName.OPPS_DETECTED_PER_MIN, MetricType.RATE, total_detected / 60.0, {"window": "60min"}),
            self._metric(MetricName.SIGNALS_GENERATED_PER_HOUR, MetricType.RATE, float(total_detected), {"window": "60min"}),
            self._metric(MetricName.EXECUTION_SUCCESS_RATE, MetricType.RATIO, success_rate, {"window": "60min"}),
            self._metric(MetricName.EXECUTION_SUCCESS_RATE, MetricType.RATIO, success_rate, {}),
            self._metric(MetricName.AVG_LATENCY_MEMPOOL_TO_DECISION_MS, MetricType.HISTOGRAM, statistics.mean(mempool_to_decision) if mempool_to_decision else 0.0, {"window": "60min"}),
            self._metric(MetricName.AVG_LATENCY_DECISION_TO_SETTLEMENT_MS, MetricType.HISTOGRAM, statistics.mean(decision_to_settlement) if decision_to_settlement else 0.0, {"window": "60min"}),
            self._metric(MetricName.AVG_LATENCY_END_TO_END_MS, MetricType.HISTOGRAM, statistics.mean(end_to_end) if end_to_end else 0.0, {"window": "60min"}),
            self._metric(MetricName.PROFIT_PER_TRADE_USDC, MetricType.GAUGE, statistics.mean(profits) if profits else 0.0, {"window": "60min"}),
            self._metric(MetricName.TOTAL_REALIZED_PNL_USDC, MetricType.GAUGE, float(sum(profits)) if profits else 0.0, {"window": "60min"}),
        ]

        if self.metrics_store is not None:
            self.metrics_store.insert_batch(metrics)
        return metrics

    def collect_sharpe_ratio(self) -> Metric:
        with self._connect_ledger() as conn:
            rows = conn.execute(
                """
                SELECT date(settled_at / 1000, 'unixepoch') AS trading_day,
                       SUM(COALESCE(realized_profit_usdc, 0) - COALESCE(gas_cost_usdc, 0)) AS daily_pnl
                FROM settlement_records
                GROUP BY trading_day
                ORDER BY trading_day ASC
                """
            ).fetchall()
        if len(rows) < 5:
            metric = self._metric(
                MetricName.SHARPE_RATIO_ANNUALIZED,
                MetricType.RATIO,
                0.0,
                {"window": "all_time", "insufficient_data": "true"},
            )
            if self.metrics_store is not None:
                self.metrics_store.insert_batch([metric])
            return metric

        daily_returns = [float(row["daily_pnl"] or 0.0) / float(INITIAL_CAPITAL_USDC) for row in rows]
        if len(daily_returns) < 2:
            sharpe = 0.0
        else:
            std_return = statistics.stdev(daily_returns)
            sharpe = 0.0 if std_return == 0 else ((statistics.mean(daily_returns) - RISK_FREE_RATE_DAILY) / std_return) * math.sqrt(365)
        metric = self._metric(MetricName.SHARPE_RATIO_ANNUALIZED, MetricType.RATIO, sharpe, {"window": "all_time"})
        if self.metrics_store is not None:
            self.metrics_store.insert_batch([metric])
        return metric

    def collect_component_health(self) -> list[Metric]:
        now_ms = int(time.time() * 1000)
        queue_depths = self.queue_manager.get_queue_depths()
        queue_depth_max = max((depth for depth in queue_depths.values() if depth >= 0), default=0)
        freshness_reports = self.freshness_monitor.benchmark_source_latency()
        freshness_ms = 0.0
        oracle_source_count = len(freshness_reports)
        if self.window_store.windows:
            recent_ages = []
            for window in self.window_store.windows.values():
                if window.window_end_ms:
                    recent_ages.append(float(max(0, now_ms - window.window_end_ms)))
            freshness_ms = max(recent_ages) if recent_ages else 0.0
        inference_p50 = 0.0
        inference_p95 = 0.0
        try:
            with self.inference_recorder._lock:
                rows = self.inference_recorder._conn.execute(
                    "SELECT inference_latency_ms FROM inference_records WHERE inference_latency_ms IS NOT NULL ORDER BY recorded_at DESC LIMIT 200"
                ).fetchall()
            latencies = [float(row[0]) for row in rows]
            if latencies:
                latencies_sorted = sorted(latencies)
                inference_p50 = float(statistics.median(latencies_sorted))
                p95_index = max(0, min(len(latencies_sorted) - 1, int(round(0.95 * (len(latencies_sorted) - 1)))))
                inference_p95 = float(latencies_sorted[p95_index])
        except Exception:
            logger.exception("INFERENCE_LATENCY_QUERY_ERROR")

        decision_time_ms = 0.0
        block_time_ms = 0.0
        gas_price_trend_pct = 0.0
        gas_price_gwei = float(getattr(self.risk_registry, "gas_price_gwei", 0.0))
        try:
            with self._connect_ledger() as conn:
                rows = conn.execute(
                    "SELECT block_timestamp, effective_gas_price_gwei FROM settlement_records WHERE block_timestamp IS NOT NULL ORDER BY settled_at DESC LIMIT 50"
                ).fetchall()
            block_times = []
            gas_prices = []
            prev_ts = None
            for row in rows:
                if row["effective_gas_price_gwei"] is not None:
                    gas_prices.append(float(row["effective_gas_price_gwei"]))
                ts = row["block_timestamp"]
                if prev_ts is not None and ts is not None:
                    block_times.append(float(abs(prev_ts - ts) * 1000))
                prev_ts = ts
            if block_times:
                block_time_ms = statistics.mean(block_times)
            if len(gas_prices) >= 2:
                baseline = statistics.mean(gas_prices[:-1]) if len(gas_prices) > 2 else gas_prices[0]
                latest = gas_prices[-1]
                gas_price_trend_pct = ((latest - baseline) / baseline * 100.0) if baseline else 0.0
        except Exception:
            logger.exception("BLOCK_TIME_QUERY_ERROR")

        if queue_depths:
            decision_time_ms = float(sum(v for v in queue_depths.values() if v >= 0) / max(len(queue_depths), 1))

        metrics = [
            self._metric(MetricName.INFERENCE_LATENCY_P50_MS, MetricType.HISTOGRAM, inference_p50, {"window": "rolling"}),
            self._metric(MetricName.INFERENCE_LATENCY_P95_MS, MetricType.HISTOGRAM, inference_p95, {"window": "rolling"}),
            self._metric(MetricName.MEMPOOL_DATA_FRESHNESS_MS, MetricType.GAUGE, freshness_ms, {"window": "current"}),
            self._metric(MetricName.AGENT_DECISION_TIME_MS, MetricType.GAUGE, decision_time_ms, {"window": "current"}),
            self._metric(MetricName.BLOCK_TIME_MS, MetricType.GAUGE, block_time_ms, {"window": "recent"}),
            self._metric(MetricName.GAS_PRICE_GWEI, MetricType.GAUGE, gas_price_gwei, {"window": "current"}),
            self._metric(MetricName.GAS_PRICE_TREND_PCT, MetricType.RATE, gas_price_trend_pct, {"window": "recent"}),
            self._metric(MetricName.ORACLE_SOURCE_COUNT, MetricType.COUNTER, float(oracle_source_count), {"window": "current"}),
            self._metric(MetricName.REDIS_QUEUE_DEPTH_MAX, MetricType.GAUGE, float(queue_depth_max), {"window": "current"}),
            self._metric(MetricName.PIPELINE_SLA_BREACHES_PER_HOUR, MetricType.RATE, self._count_sla_breaches_per_hour(), {"window": "1h"}),
        ]
        if self.metrics_store is not None:
            self.metrics_store.insert_batch(metrics)
        return metrics

    def _count_sla_breaches_per_hour(self) -> float:
        try:
            keys = self.queue_manager._client.keys("flashix:correlation:*")
            now_ms = int(time.time() * 1000)
            breaches = 0
            for key in keys:
                record = self.queue_manager._client.hgetall(key)
                created = int(record.get("created_at", "0") or 0)
                current_stage = record.get("current_stage", "UNKNOWN")
                if created and now_ms - created > 30_000 and current_stage != "SETTLEMENT_COMPLETED":
                    breaches += 1
            return float(breaches)
        except Exception:
            return 0.0

    def collect_risk_metrics(self) -> list[Metric]:
        snapshot = self.risk_registry.get_snapshot()
        open_breakers = len(snapshot.open_breakers)
        daily_pnl = float(snapshot.daily_pnl_usdc)
        drawdown_pct, current_pnl, peak_pnl = self._calculate_drawdown_from_ledger()
        loss_cap = float(abs(ALERT_DAILY_PNL_WARN_USDC))
        utilization = 0.0 if loss_cap == 0 else max(0.0, min(100.0, abs(daily_pnl) / loss_cap * 100.0))
        metrics = [
            self._metric(MetricName.CONCURRENT_POSITIONS, MetricType.GAUGE, float(snapshot.concurrent_positions), {"window": "current"}),
            self._metric(MetricName.COLLATERAL_RATIO, MetricType.GAUGE, float(snapshot.current_collateral_ratio), {"window": "current"}),
            self._metric(MetricName.DAILY_PNL_USDC, MetricType.GAUGE, daily_pnl, {"window": "current"}),
            self._metric(MetricName.DRAWDOWN_FROM_PEAK_PCT, MetricType.GAUGE, drawdown_pct, {"window": "current"}),
            self._metric(MetricName.DAILY_LOSS_CAP_UTILIZATION_PCT, MetricType.RATIO, utilization, {"window": "current"}),
            self._metric(MetricName.OPEN_CIRCUIT_BREAKERS_COUNT, MetricType.GAUGE, float(open_breakers), {"window": "current"}),
            self._metric(MetricName.PORTFOLIO_HEAT, MetricType.GAUGE, float(snapshot.portfolio_heat), {"window": "current"}),
        ]
        if self.metrics_store is not None:
            self.metrics_store.insert_batch(metrics)
        return metrics

    def _calculate_drawdown_from_ledger(self) -> tuple[float, float, float]:
        with self._connect_ledger() as conn:
            rows = conn.execute(
                """
                SELECT settled_at, COALESCE(realized_profit_usdc, 0) AS realized_profit, COALESCE(gas_cost_usdc, 0) AS gas_cost
                FROM settlement_records
                WHERE receipt_status = 'CONFIRMED'
                ORDER BY settled_at ASC
                """
            ).fetchall()
        running_pnl = 0.0
        peak_pnl = 0.0
        current_drawdown = 0.0
        max_drawdown = 0.0
        current_pnl = 0.0
        for row in rows:
            running_pnl += float(row["realized_profit"] or 0.0) - float(row["gas_cost"] or 0.0)
            peak_pnl = max(peak_pnl, running_pnl)
            if peak_pnl > 0:
                current_drawdown = max(0.0, (peak_pnl - running_pnl) / peak_pnl * 100.0)
                max_drawdown = max(max_drawdown, current_drawdown)
            current_pnl = running_pnl
        return current_drawdown, current_pnl, peak_pnl

    def collect_all(self) -> list[Metric]:
        metrics = self.collect_execution_metrics() + [self.collect_sharpe_ratio()] + self.collect_component_health() + self.collect_risk_metrics()
        deduped = self._dedupe(metrics)
        snapshot = {metric_snapshot_key(metric): metric for metric in deduped}
        self.current_snapshot = snapshot
        return deduped
