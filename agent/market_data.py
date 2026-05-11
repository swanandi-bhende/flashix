"""
Market Data Service: Live oracle aggregation, freshness monitoring, and REST API.

This module serves as the master definition file for all market data structures,
enums, and constants used throughout the market data pipeline. All consumers
(oracle clients, aggregator, window store, REST API, agent) import from here
to ensure type consistency and single source of truth.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Deque, Literal, Optional

_logger = logging.getLogger(__name__)


# ===== ENUMS =====

class OracleSource(str, Enum):
    """Oracle data sources, in priority order for fallback cascade."""
    PYTH = "PYTH"
    CHAINLINK = "CHAINLINK"
    ONE_INCH = "ONE_INCH"
    DEX_DIRECT = "DEX_DIRECT"


class FallbackState(str, Enum):
    """Oracle health state tracking for fallback decisions."""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class DataQualityLevel(str, Enum):
    """Consensus data quality classification."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNAVAILABLE = "UNAVAILABLE"


# ===== FRESHNESS CONSTANTS =====

MAX_STALENESS_MS: int = 500
"""Maximum acceptable data staleness in milliseconds. Target <500ms staleness."""

PYTH_TIMEOUT_MS: int = 300
"""Pyth WebSocket subscription read timeout."""

CHAINLINK_TIMEOUT_MS: int = 400
"""Chainlink contract call timeout."""

ONE_INCH_TIMEOUT_MS: int = 350
"""1inch API call timeout."""

MANIPULATION_DETECTION_THRESHOLD_PCT: float = 0.5
"""If any oracle deviates >0.5% from consensus, flag as potential manipulation."""

MIN_SOURCES_FOR_EXECUTION: int = 2
"""Minimum number of valid oracle sources required to proceed with execution."""

MAX_PRICE_SAMPLES: int = 1000
"""Maximum number of aggregated price samples to keep in sliding window."""

WINDOW_DURATION_SECONDS: int = 600
"""Size of rolling history window: 10 minutes."""


# ===== DATA STRUCTURES =====

@dataclass(frozen=True)
class RawPriceSample:
    """
    Raw price data from a single oracle source before aggregation.
    
    Attributes:
        source: Which oracle provided this sample (PYTH, CHAINLINK, etc.)
        symbol: Trading pair symbol (e.g., "BTC-USD-PERP")
        mark_price: Current perpetual swap mark price
        index_price: Underlying index price
        funding_rate: Current 8-hour funding rate
        funding_rate_annualized: Annualized funding rate
        collateral_ratio: Collateral adequacy ratio
        bid_price: Best bid price from DEX
        ask_price: Best ask price from DEX
        mid_price: (bid_price + ask_price) / 2
        spread_bps: Bid-ask spread in basis points
        fetched_at_ms: Timestamp when we fetched this sample (epoch ms)
        source_timestamp_ms: Timestamp the oracle assigned to this data (epoch ms)
        staleness_ms: Computed as fetched_at_ms - source_timestamp_ms
        fetch_latency_ms: How long the network fetch took
        is_valid: Passed initial validation checks
        validation_failure_reason: Why validation failed (if is_valid=False)
    """
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
    """
    Consensus market state derived from aggregating multiple oracle sources.
    
    Attributes:
        symbol: Trading pair symbol
        consensus_price: Median price across all valid sources
        price_std_dev: Standard deviation of prices from valid sources
        max_deviation_pct: Largest deviation of any source from consensus (flags manipulation)
        funding_rate_consensus: Median funding rate across sources
        collateral_ratio_consensus: Median collateral ratio across sources
        sources_used: Which oracles contributed to this consensus
        sources_failed: Which oracles were unavailable/invalid
        data_quality: Classification of consensus reliability
        aggregated_at_ms: Timestamp when we computed this consensus
        oldest_source_staleness_ms: Staleness of the oldest sample in consensus
    """
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
    """
    Sliding window of aggregated market states for a single symbol.
    
    Attributes:
        symbol: Trading pair symbol
        samples: Deque of up to MAX_PRICE_SAMPLES AggregatedMarketState entries
        window_start_ms: Timestamp of oldest sample in window
        window_end_ms: Timestamp of newest sample in window
        sample_count: Number of samples currently in window
    """
    symbol: str
    samples: Deque[AggregatedMarketState] = field(default_factory=lambda: deque(maxlen=MAX_PRICE_SAMPLES))
    window_start_ms: int = 0
    window_end_ms: int = 0
    sample_count: int = 0


@dataclass(frozen=True)
class FreshnessViolation:
    """Record of a staleness threshold violation."""
    violation_id: str
    source: OracleSource
    symbol: str
    staleness_ms: int
    threshold_ms: int
    fetch_latency_ms: float
    recorded_at: int


@dataclass(frozen=True)
class DataGap:
    """Detected gap in market data (missing samples)."""
    symbol: str
    gap_start_ms: int
    gap_end_ms: int
    duration_ms: int
    missing_samples_estimate: int


@dataclass(frozen=True)
class LatencyBenchmark:
    """Latency statistics for a single oracle source."""
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    sample_count: int


@dataclass(frozen=True)
class FreshnessReport:
    """Complete freshness analysis for monitoring and post-trade analysis."""
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
    """Live slippage estimate from DEX swap simulation."""
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
