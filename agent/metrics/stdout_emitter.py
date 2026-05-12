from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from typing import Callable

from colorama import Fore, Style, init as colorama_init

from agent.metrics import Metric, MetricName, ALERT_EXECUTION_SUCCESS_RATE_MIN, ALERT_INFERENCE_LATENCY_P95_MAX_MS, ALERT_MEMPOOL_FRESHNESS_MAX_MS, ALERT_OPEN_BREAKERS_CRITICAL, MAX_CONCURRENT_POSITIONS

colorama_init()


class StdoutEmitter:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger()
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def emit_json(self, metrics: list[Metric]) -> None:
        for metric in metrics:
            self.logger.info(
                json.dumps(
                    {
                        "event": "METRIC",
                        "name": metric.name.value,
                        "value": metric.value,
                        "labels": metric.labels,
                        "component": metric.component,
                        "ts": metric.timestamp_ms,
                    },
                    sort_keys=True,
                )
            )

    def emit_dashboard_table(self, snapshot: dict[str, Metric]) -> None:
        def pick(metric_name: MetricName) -> float:
            for metric in snapshot.values():
                if metric.name == metric_name:
                    return float(metric.value)
            return 0.0

        now_text = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "\033[2J\033[H",
            f"FLASHIX LIVE MONITOR — {now_text} UTC",
            "",
            "Execution",
            self._row("opportunities/min", pick(MetricName.OPPS_DETECTED_PER_MIN)),
            self._row("success_rate", pick(MetricName.EXECUTION_SUCCESS_RATE), threshold=ALERT_EXECUTION_SUCCESS_RATE_MIN, pct=True),
            self._row("avg_latency_ms", pick(MetricName.AVG_LATENCY_END_TO_END_MS), threshold=3000.0),
            self._row("profit_per_trade", pick(MetricName.PROFIT_PER_TRADE_USDC)),
            self._row("sharpe_ratio", pick(MetricName.SHARPE_RATIO_ANNUALIZED)),
            "",
            "Health",
            self._row("inference_p95_ms", pick(MetricName.INFERENCE_LATENCY_P95_MS), healthy_max=1000.0, warning_max=3000.0),
            self._row("mempool_freshness_ms", pick(MetricName.MEMPOOL_DATA_FRESHNESS_MS), healthy_max=ALERT_MEMPOOL_FRESHNESS_MAX_MS),
            self._row("gas_price_gwei", pick(MetricName.GAS_PRICE_GWEI)),
            self._row("queue_depth", pick(MetricName.REDIS_QUEUE_DEPTH_MAX), healthy_max=25.0, warning_max=ALERT_QUEUE_DEPTH_MAX),
            self._row("open_breakers", pick(MetricName.OPEN_CIRCUIT_BREAKERS_COUNT), healthy_max=0.0, warning_max=float(ALERT_OPEN_BREAKERS_CRITICAL)),
            "",
            "Risk",
            self._row("concurrent_positions", pick(MetricName.CONCURRENT_POSITIONS), healthy_max=float(MAX_CONCURRENT_POSITIONS), warning_max=float(MAX_CONCURRENT_POSITIONS)),
            self._row("daily_pnl", pick(MetricName.DAILY_PNL_USDC)),
            self._row("drawdown_pct", pick(MetricName.DRAWDOWN_FROM_PEAK_PCT), healthy_max=15.0, warning_max=30.0),
            self._row("portfolio_heat", pick(MetricName.PORTFOLIO_HEAT), healthy_max=0.6, warning_max=0.8),
        ]
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

    def _row(self, label: str, value: float, threshold: float | None = None, healthy_max: float | None = None, warning_max: float | None = None, pct: bool = False) -> str:
        color = Fore.GREEN
        if threshold is not None and value < threshold:
            color = Fore.RED
        if healthy_max is not None and value >= healthy_max:
            color = Fore.YELLOW
        if warning_max is not None and value >= warning_max:
            color = Fore.RED
        rendered = f"{value:.2f}%" if pct else f"{value:.2f}"
        return f"{color}{label:<28} {rendered:>12}{Style.RESET_ALL}"
