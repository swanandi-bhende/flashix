from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from datetime import datetime

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from agent.metrics import Metric, MetricName, MetricType, PROMETHEUS_PORT

logger = logging.getLogger(__name__)

opps_detected_counter = Counter("flashix_opportunities_detected_total", "Total opportunities detected from mempool", ["symbol"])
execution_success_gauge = Gauge("flashix_execution_success_rate", "Rolling execution success rate", ["window"])
inference_latency_histogram = Histogram("flashix_inference_latency_ms", "TEE inference latency in milliseconds", buckets=[100, 250, 500, 1000, 2000, 3000, 5000, 10000])
profit_per_trade_gauge = Gauge("flashix_profit_per_trade_usdc", "Average realized profit per trade in USDC")
daily_pnl_gauge = Gauge("flashix_daily_pnl_usdc", "Current session daily P&L in USDC")
drawdown_gauge = Gauge("flashix_drawdown_pct", "Current drawdown from peak profit percentage")
sharpe_ratio_gauge = Gauge("flashix_sharpe_ratio", "Annualized Sharpe ratio")
concurrent_positions_gauge = Gauge("flashix_concurrent_positions", "Current number of open positions")
circuit_breakers_gauge = Gauge("flashix_open_circuit_breakers", "Number of currently open circuit breakers")


class PrometheusExporter:
    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = enabled if enabled is not None else os.getenv("METRICS_PROMETHEUS_ENABLED", "false").lower() == "true"
        self._started = False
        self._counter_cache: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        if self.enabled:
            self.start_server()

    def start_server(self) -> None:
        if self._started:
            return
        start_http_server(PROMETHEUS_PORT)
        self._started = True
        logger.info("PROMETHEUS_EXPORTER_STARTED: http://localhost:%s/metrics", PROMETHEUS_PORT)

    def sync_from_snapshot(self, snapshot: dict[str, Metric]) -> None:
        for metric in snapshot.values():
            if metric.name == MetricName.OPPS_DETECTED_PER_MIN:
                symbol = metric.labels.get("symbol", "all")
                value = float(metric.value)
                key = (symbol, tuple(sorted(metric.labels.items())))
                previous = self._counter_cache.get(key, 0.0)
                delta = max(0.0, value - previous)
                opps_detected_counter.labels(symbol=symbol).inc(delta)
                self._counter_cache[key] = value
            elif metric.name == MetricName.EXECUTION_SUCCESS_RATE:
                execution_success_gauge.labels(window=metric.labels.get("window", "all")).set(metric.value)
            elif metric.name == MetricName.INFERENCE_LATENCY_P95_MS:
                inference_latency_histogram.observe(metric.value)
            elif metric.name == MetricName.PROFIT_PER_TRADE_USDC:
                profit_per_trade_gauge.set(metric.value)
            elif metric.name == MetricName.DAILY_PNL_USDC:
                daily_pnl_gauge.set(metric.value)
            elif metric.name == MetricName.DRAWDOWN_FROM_PEAK_PCT:
                drawdown_gauge.set(metric.value)
            elif metric.name == MetricName.SHARPE_RATIO_ANNUALIZED:
                sharpe_ratio_gauge.set(metric.value)
            elif metric.name == MetricName.CONCURRENT_POSITIONS:
                concurrent_positions_gauge.set(metric.value)
            elif metric.name == MetricName.OPEN_CIRCUIT_BREAKERS_COUNT:
                circuit_breakers_gauge.set(metric.value)


_GLOBAL_EXPORTER = PrometheusExporter()


def start_prometheus_server() -> PrometheusExporter:
    _GLOBAL_EXPORTER.start_server()
    return _GLOBAL_EXPORTER
