from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Optional

from agent.risk_manager import MAX_CONCURRENT_POSITIONS

__path__ = [str(Path(__file__).with_name("metrics"))]


class MetricType(str, Enum):
    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    RATE = "RATE"
    RATIO = "RATIO"


class MetricName(str, Enum):
    OPPS_DETECTED_PER_MIN = "OPPS_DETECTED_PER_MIN"
    SIGNALS_GENERATED_PER_HOUR = "SIGNALS_GENERATED_PER_HOUR"
    EXECUTION_SUCCESS_RATE = "EXECUTION_SUCCESS_RATE"
    AVG_LATENCY_MEMPOOL_TO_DECISION_MS = "AVG_LATENCY_MEMPOOL_TO_DECISION_MS"
    AVG_LATENCY_DECISION_TO_SETTLEMENT_MS = "AVG_LATENCY_DECISION_TO_SETTLEMENT_MS"
    AVG_LATENCY_END_TO_END_MS = "AVG_LATENCY_END_TO_END_MS"
    PROFIT_PER_TRADE_USDC = "PROFIT_PER_TRADE_USDC"
    SHARPE_RATIO_ANNUALIZED = "SHARPE_RATIO_ANNUALIZED"
    WIN_RATE_PCT = "WIN_RATE_PCT"
    TOTAL_REALIZED_PNL_USDC = "TOTAL_REALIZED_PNL_USDC"
    INFERENCE_LATENCY_P50_MS = "INFERENCE_LATENCY_P50_MS"
    INFERENCE_LATENCY_P95_MS = "INFERENCE_LATENCY_P95_MS"
    MEMPOOL_DATA_FRESHNESS_MS = "MEMPOOL_DATA_FRESHNESS_MS"
    AGENT_DECISION_TIME_MS = "AGENT_DECISION_TIME_MS"
    BLOCK_TIME_MS = "BLOCK_TIME_MS"
    GAS_PRICE_GWEI = "GAS_PRICE_GWEI"
    GAS_PRICE_TREND_PCT = "GAS_PRICE_TREND_PCT"
    ORACLE_SOURCE_COUNT = "ORACLE_SOURCE_COUNT"
    REDIS_QUEUE_DEPTH_MAX = "REDIS_QUEUE_DEPTH_MAX"
    PIPELINE_SLA_BREACHES_PER_HOUR = "PIPELINE_SLA_BREACHES_PER_HOUR"
    CONCURRENT_POSITIONS = "CONCURRENT_POSITIONS"
    COLLATERAL_RATIO = "COLLATERAL_RATIO"
    DAILY_PNL_USDC = "DAILY_PNL_USDC"
    DRAWDOWN_FROM_PEAK_PCT = "DRAWDOWN_FROM_PEAK_PCT"
    DAILY_LOSS_CAP_UTILIZATION_PCT = "DAILY_LOSS_CAP_UTILIZATION_PCT"
    OPEN_CIRCUIT_BREAKERS_COUNT = "OPEN_CIRCUIT_BREAKERS_COUNT"
    PORTFOLIO_HEAT = "PORTFOLIO_HEAT"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True)
class Metric:
    name: MetricName
    type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp_ms: int = 0
    component: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Alert:
    alert_id: str
    severity: AlertSeverity
    metric_name: MetricName
    current_value: float
    threshold_value: float
    message: str
    triggered_at: int
    resolved_at: Optional[int]
    acknowledged: bool


ALERT_EXECUTION_SUCCESS_RATE_MIN = 0.90
ALERT_INFERENCE_LATENCY_P95_MAX_MS = 3000.0
ALERT_MEMPOOL_FRESHNESS_MAX_MS = 800.0
ALERT_DAILY_PNL_WARN_USDC = Decimal("-25.0")
ALERT_DRAWDOWN_WARN_PCT = 15.0
ALERT_QUEUE_DEPTH_MAX = 50.0
ALERT_GAS_PRICE_SPIKE_PCT = 25.0
ALERT_OPEN_BREAKERS_CRITICAL = 3.0

PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))
METRICS_API_PORT = int(os.getenv("METRICS_API_PORT", "8005"))
METRICS_COLLECTION_INTERVAL_SECONDS = 5
METRICS_DASHBOARD_INTERVAL_SECONDS = 10
METRICS_PROFILER_INTERVAL_SECONDS = 300

# 0G Compute / trading assumptions used across the monitoring layer.
INITIAL_CAPITAL_USDC = Decimal("1000.0")
RISK_FREE_RATE_DAILY = float((Decimal("1.045") ** (Decimal(1) / Decimal(365))) - Decimal(1))

DEFAULT_METRIC_COMPONENT = "metrics"


def metric_snapshot_key(metric: Metric) -> str:
    labels = ",".join(f"{key}={value}" for key, value in sorted(metric.labels.items()))
    return f"{metric.name.value}|{labels}"


def metric_name_key(name: MetricName, labels: Optional[dict[str, str]] = None) -> str:
    labels = labels or {}
    labels_str = ",".join(f"{key}={value}" for key, value in sorted(labels.items()))
    return f"{name.value}|{labels_str}"
