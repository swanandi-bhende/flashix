"""Shared market data types, constants, and service primitives."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Deque, Optional


class OracleSource(str, Enum):
    PYTH = "PYTH"
    CHAINLINK = "CHAINLINK"
    ONE_INCH = "ONE_INCH"
    DEX_DIRECT = "DEX_DIRECT"


class FallbackState(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class DataQualityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNAVAILABLE = "UNAVAILABLE"


MAX_STALENESS_MS: int = 500
PYTH_TIMEOUT_MS: int = 300
CHAINLINK_TIMEOUT_MS: int = 400
ONE_INCH_TIMEOUT_MS: int = 350
MANIPULATION_DETECTION_THRESHOLD_PCT: float = 0.5
MIN_SOURCES_FOR_EXECUTION: int = 2
MAX_PRICE_SAMPLES: int = 1000
WINDOW_DURATION_SECONDS: int = 600


@dataclass(frozen=True)
class RawPriceSample:
    source: OracleSource
    symbol: str
    mark_price: Decimal
    index_price: Decimal
    funding_rate: Decimal
    funding_rate_annualized: Decimal
    collateral_ratio: Decimal
    bid_price: Decimal
    ask_price: Decimal
    mid_price: Decimal
    spread_bps: float
    fetched_at_ms: int
    source_timestamp_ms: int
    staleness_ms: int
    fetch_latency_ms: float
    is_valid: bool
    validation_failure_reason: Optional[str] = None


@dataclass(frozen=True)
class AggregatedMarketState:
    symbol: str
    consensus_price: Decimal
    price_std_dev: Decimal
    max_deviation_pct: float
    funding_rate_consensus: Decimal
    collateral_ratio_consensus: Decimal
    sources_used: list[OracleSource]
    sources_failed: list[OracleSource]
    data_quality: DataQualityLevel
    aggregated_at_ms: int
    oldest_source_staleness_ms: int


@dataclass
class MarketStateWindow:
    symbol: str
    samples: Deque[AggregatedMarketState] = field(default_factory=lambda: deque(maxlen=MAX_PRICE_SAMPLES))
    window_start_ms: int = 0
    window_end_ms: int = 0
    sample_count: int = 0


@dataclass(frozen=True)
class FreshnessViolation:
    violation_id: str
    source: OracleSource
    symbol: str
    staleness_ms: int
    threshold_ms: int
    fetch_latency_ms: float
    recorded_at: int


@dataclass(frozen=True)
class DataGap:
    symbol: str
    gap_start_ms: int
    gap_end_ms: int
    duration_ms: int
    missing_samples_estimate: int


@dataclass(frozen=True)
class LatencyBenchmark:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    sample_count: int


@dataclass(frozen=True)
class FreshnessReport:
    total_samples: int
    violation_count: int
    violation_rate_pct: float
    avg_staleness_ms: float
    p95_staleness_ms: float
    sources_ranked_by_freshness: list[tuple[OracleSource, float]]
    data_gaps: list[DataGap]
    recommendation: str


@dataclass(frozen=True)
class SlippageEstimate:
    price_impact_pct: float
    recommended_slippage_tolerance_pct: float
    liquidity_score: float


__all__ = [
    "OracleSource",
    "FallbackState",
    "DataQualityLevel",
    "RawPriceSample",
    "AggregatedMarketState",
    "MarketStateWindow",
    "FreshnessViolation",
    "DataGap",
    "LatencyBenchmark",
    "FreshnessReport",
    "SlippageEstimate",
    "MAX_STALENESS_MS",
    "PYTH_TIMEOUT_MS",
    "CHAINLINK_TIMEOUT_MS",
    "ONE_INCH_TIMEOUT_MS",
    "MANIPULATION_DETECTION_THRESHOLD_PCT",
    "MIN_SOURCES_FOR_EXECUTION",
    "MAX_PRICE_SAMPLES",
    "WINDOW_DURATION_SECONDS",
]
