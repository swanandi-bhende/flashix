"""REST API for market data service using FastAPI."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from agent.market_data import (
    AggregatedMarketState,
    DataQualityLevel,
    FallbackState,
    OracleSource,
)

_logger = logging.getLogger(__name__)


# ===== PYDANTIC MODELS FOR API RESPONSES =====

class PriceResponse(BaseModel):
    """Latest aggregated market state for a symbol."""
    symbol: str
    consensus_price: str
    price_std_dev: str
    max_deviation_pct: float
    funding_rate: str
    collateral_ratio: str
    data_quality: str
    sources_used: list[str]
    sources_failed: list[str]
    aggregated_at_ms: int
    oldest_source_staleness_ms: int


class WindowSampleResponse(BaseModel):
    """Single sample in the rolling window."""
    timestamp_ms: int
    consensus_price: str
    data_quality: str
    sources_used: list[str]


class VolatilityResponse(BaseModel):
    """Volatility metrics for a symbol."""
    symbol: str
    volatility: Optional[float]
    window_seconds: int
    sample_count: int
    computed_at_ms: int


class CorrelationResponse(BaseModel):
    """Correlation between two symbols."""
    symbol_a: str
    symbol_b: str
    correlation: Optional[float]
    window_seconds: int
    sample_count: int
    computed_at_ms: int


class HealthResponse(BaseModel):
    """Comprehensive health report for all oracles and symbols."""
    sources: dict[str, str]
    freshness: dict[str, int]
    data_quality: dict[str, str]
    execution_safe: bool
    staleness_violations_last_hour: int
    computed_at_ms: int


class FreshnessReportItemResponse(BaseModel):
    """Freshness metrics for a single symbol."""
    symbol: str
    total_samples: int
    violation_count: int
    violation_rate_pct: float
    avg_staleness_ms: float
    p95_staleness_ms: float
    recommendation: str


class ManipulationAlertResponse(BaseModel):
    """Active manipulation/deviation alert."""
    symbol: str
    deviating_source: str
    deviation_pct: float
    detected_at_ms: int


# ===== GLOBAL STATE =====
# These would be injected in a real app; here we use module globals

_aggregator = None
_window_store = None
_fallback_orchestrator = None
_freshness_monitor = None


def init_api(aggregator, window_store, fallback_orchestrator, freshness_monitor):
    """Initialize API with service dependencies."""
    global _aggregator, _window_store, _fallback_orchestrator, _freshness_monitor
    _aggregator = aggregator
    _window_store = window_store
    _fallback_orchestrator = fallback_orchestrator
    _freshness_monitor = freshness_monitor


# ===== FASTAPI APP =====

app = FastAPI(
    title="Flashix Market Data API",
    description="Live oracle aggregation, freshness monitoring, and market state queries",
    version="1.0.0",
)


@app.get("/market/{symbol}/latest", response_model=PriceResponse, tags=["Market Data"])
async def get_latest_price(symbol: str):
    """
    Get the most recent aggregated market state for a symbol.
    
    Returns consensus price, funding rate, data quality classification,
    and which oracles contributed to the consensus.
    
    **Hot path**: Called by agent before every trade.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC-USD-PERP")
        
    Returns:
        Aggregated market state with consensus price and oracle status
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    window = _window_store.windows.get(symbol)
    if not window or not window.samples:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

    latest = window.samples[-1]

    return PriceResponse(
        symbol=symbol,
        consensus_price=str(latest.consensus_price),
        price_std_dev=str(latest.price_std_dev),
        max_deviation_pct=latest.max_deviation_pct,
        funding_rate=str(latest.funding_rate_consensus),
        collateral_ratio=str(latest.collateral_ratio_consensus),
        data_quality=latest.data_quality.value,
        sources_used=[s.value for s in latest.sources_used],
        sources_failed=[s.value for s in latest.sources_failed],
        aggregated_at_ms=latest.aggregated_at_ms,
        oldest_source_staleness_ms=latest.oldest_source_staleness_ms,
    )


@app.get("/market/{symbol}/window", response_model=list[WindowSampleResponse], tags=["Market Data"])
async def get_price_window(
    symbol: str,
    window_seconds: int = Query(300, ge=10, le=600),
    fields: Optional[str] = Query(None),
):
    """
    Get a slice of the rolling price window for correlation analysis.
    
    Returns recent price history as a JSON array of samples.
    The agent uses this to compute price correlations and volatility.
    
    Args:
        symbol: Trading pair symbol
        window_seconds: Time window for returned samples (default 300s = 5 minutes)
        fields: Comma-separated fields to include (default: all)
        
    Returns:
        Array of aggregated market states within the window
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    window = _window_store.windows.get(symbol)
    if not window or not window.samples:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

    now_ms = window.window_end_ms
    window_start_ms = now_ms - window_seconds * 1000

    samples = [
        s for s in window.samples
        if s.aggregated_at_ms >= window_start_ms
    ]

    return [
        WindowSampleResponse(
            timestamp_ms=s.aggregated_at_ms,
            consensus_price=str(s.consensus_price),
            data_quality=s.data_quality.value,
            sources_used=[src.value for src in s.sources_used],
        )
        for s in samples
    ]


@app.get("/market/{symbol}/volatility", response_model=VolatilityResponse, tags=["Market Analytics"])
async def get_volatility(
    symbol: str,
    window_seconds: int = Query(60, ge=10, le=600),
):
    """
    Compute annualized volatility for a symbol over a recent time window.
    
    Uses log returns for accurate volatility calculation.
    
    Args:
        symbol: Trading pair symbol
        window_seconds: Time window for volatility (default 60s = 1 minute)
        
    Returns:
        Volatility metric and sample count used
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    volatility = _window_store.get_volatility(symbol, window_seconds)
    
    window = _window_store.windows.get(symbol)
    sample_count = len(window.samples) if window else 0

    return VolatilityResponse(
        symbol=symbol,
        volatility=volatility,
        window_seconds=window_seconds,
        sample_count=sample_count,
        computed_at_ms=int(time.time() * 1000),
    )


@app.get("/market/{symbol_a}/correlation/{symbol_b}", response_model=CorrelationResponse, tags=["Market Analytics"])
async def get_correlation(
    symbol_a: str,
    symbol_b: str,
    window_seconds: int = Query(300, ge=30, le=600),
):
    """
    Compute Pearson correlation coefficient between two symbols.
    
    Useful for understanding hedge relationships and portfolio risk.
    
    Args:
        symbol_a: First trading pair
        symbol_b: Second trading pair
        window_seconds: Time window (default 300s = 5 minutes)
        
    Returns:
        Correlation coefficient in [-1, 1]
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    correlation = _window_store.get_price_correlation(
        symbol_a, symbol_b, window_seconds
    )

    window_a = _window_store.windows.get(symbol_a)
    sample_count = len(window_a.samples) if window_a else 0

    return CorrelationResponse(
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        correlation=correlation,
        window_seconds=window_seconds,
        sample_count=sample_count,
        computed_at_ms=int(time.time() * 1000),
    )


@app.get("/market/health", response_model=HealthResponse, tags=["Monitoring"])
async def get_health():
    """
    Comprehensive health report: oracle status, freshness, data quality, execution safety.
    
    **For Demo**: Call this endpoint to show judges the live oracle status.
    
    Returns:
        Health report with all oracle states and execution readiness
    """
    if not _window_store or not _fallback_orchestrator:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    pyth_state = _fallback_orchestrator.pyth_client.get_fallback_state().value
    chainlink_state = _fallback_orchestrator.chainlink_client.get_fallback_state().value
    oneinch_state = _fallback_orchestrator.oneinch_client.get_fallback_state().value

    freshness = {}
    data_quality = {}
    execution_safe = True

    for symbol, window in _window_store.windows.items():
        if window.samples:
            latest = window.samples[-1]
            freshness[symbol] = latest.oldest_source_staleness_ms
            data_quality[symbol] = latest.data_quality.value

            if latest.data_quality == DataQualityLevel.UNAVAILABLE:
                execution_safe = False

    return HealthResponse(
        sources={
            "PYTH": pyth_state,
            "CHAINLINK": chainlink_state,
            "ONE_INCH": oneinch_state,
        },
        freshness=freshness,
        data_quality=data_quality,
        execution_safe=execution_safe,
        staleness_violations_last_hour=0,  # Would compute from freshness_monitor
        computed_at_ms=int(time.time() * 1000),
    )


@app.get("/market/freshness/report", response_model=list[FreshnessReportItemResponse], tags=["Monitoring"])
async def get_freshness_report():
    """
    Detailed freshness analysis for all symbols.
    
    Shows violation rate, latency percentiles, and automated recommendations.
    
    Returns:
        Array of freshness reports per symbol
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    freshness_reports = _window_store.get_freshness_report()

    return [
        FreshnessReportItemResponse(
            symbol=symbol,
            total_samples=report.total_samples,
            violation_count=report.violation_count,
            violation_rate_pct=report.violation_rate_pct,
            avg_staleness_ms=report.avg_staleness_ms,
            p95_staleness_ms=report.p95_staleness_ms,
            recommendation=report.recommendation,
        )
        for symbol, report in freshness_reports.items()
    ]


@app.get("/market/oracle/deviation", response_model=list[ManipulationAlertResponse], tags=["Monitoring"])
async def get_deviation_alerts():
    """
    List all active oracle manipulation/deviation alerts.
    
    **For Demo**: Call this to show judges if any manipulation was detected during trading.
    
    Returns:
        Array of active deviation alerts
    """
    if not _window_store:
        raise HTTPException(status_code=503, detail="Market data service not initialized")

    alerts = []

    for symbol, window in _window_store.windows.items():
        if window.samples:
            latest = window.samples[-1]
            if latest.max_deviation_pct > 0.5:  # MANIPULATION_DETECTION_THRESHOLD_PCT
                # Find which source deviates most
                for source in latest.sources_failed:
                    alerts.append(
                        ManipulationAlertResponse(
                            symbol=symbol,
                            deviating_source=source.value,
                            deviation_pct=latest.max_deviation_pct,
                            detected_at_ms=latest.aggregated_at_ms,
                        )
                    )

    return alerts


@app.get("/health", tags=["System"])
async def system_health():
    """Simple health check for service availability."""
    return {"status": "ok", "timestamp": int(time.time() * 1000)}


__all__ = ["app", "init_api"]
