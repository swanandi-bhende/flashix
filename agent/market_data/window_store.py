"""In-memory sliding window store with statistical query methods."""

from __future__ import annotations

import logging
import math
import threading
from typing import Optional

import numpy as np

from agent.market_data import (
    AggregatedMarketState,
    FreshnessReport,
    MarketStateWindow,
    MAX_PRICE_SAMPLES,
)

_logger = logging.getLogger(__name__)


class MarketStateWindowStore:
    """
    Maintains 1000-sample, 10-minute rolling windows of AggregatedMarketState
    for every tracked symbol and exposes statistical query methods for volatility
    and correlation analysis.
    """

    def __init__(self, tracked_symbols: list[str]):
        """
        Initialize window store.
        
        Args:
            tracked_symbols: List of symbols to track (e.g., ["BTC-USD-PERP", "ETH-USD-PERP"])
        """
        self.windows: dict[str, MarketStateWindow] = {
            symbol: MarketStateWindow(symbol=symbol)
            for symbol in tracked_symbols
        }
        self._lock = threading.RLock()

    def record(self, state: AggregatedMarketState) -> None:
        """
        Record an aggregated market state in the sliding window.
        
        Args:
            state: AggregatedMarketState to record
        """
        with self._lock:
            window = self.windows.get(state.symbol)
            if not window:
                window = MarketStateWindow(symbol=state.symbol)
                self.windows[state.symbol] = window

            window.samples.append(state)
            window.sample_count = len(window.samples)
            window.window_end_ms = state.aggregated_at_ms

            if window.window_start_ms == 0:
                window.window_start_ms = state.aggregated_at_ms

    def get_volatility(
        self, symbol: str, window_seconds: int = 60
    ) -> Optional[float]:
        """
        Compute annualized volatility using log returns over a time window.
        
        Volatility = std(log_returns) * sqrt(samples_per_second * window_seconds)
        
        Args:
            symbol: Trading pair symbol
            window_seconds: Time window for volatility calculation
            
        Returns:
            Annualized volatility, or None if insufficient samples
        """
        with self._lock:
            window = self.windows.get(symbol)
            if not window or len(window.samples) < 10:
                return None

            # Filter samples to the requested window
            now_ms = window.window_end_ms
            window_start_ms = now_ms - window_seconds * 1000

            samples = [
                s for s in window.samples
                if s.aggregated_at_ms >= window_start_ms
            ]

            if len(samples) < 2:
                return None

            # Compute log returns
            prices = [s.consensus_price for s in samples]
            log_returns = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 0 and prices[i] > 0:
                    log_return = float(math.log(prices[i] / prices[i - 1]))
                    log_returns.append(log_return)

            if len(log_returns) < 2:
                return None

            # Compute volatility
            std_dev = float(np.std(log_returns))
            if window_seconds > 0:
                samples_per_second = len(samples) / window_seconds
                volatility = std_dev * math.sqrt(samples_per_second * window_seconds)
            else:
                volatility = std_dev

            return volatility

    def get_price_correlation(
        self, symbol_a: str, symbol_b: str, window_seconds: int = 300
    ) -> Optional[float]:
        """
        Compute Pearson correlation coefficient between two symbols' price movements.
        
        Args:
            symbol_a: First trading pair
            symbol_b: Second trading pair
            window_seconds: Time window for correlation
            
        Returns:
            Correlation coefficient in [-1, 1], or None if insufficient samples
        """
        with self._lock:
            window_a = self.windows.get(symbol_a)
            window_b = self.windows.get(symbol_b)

            if not window_a or not window_b:
                return None

            # Get samples within window
            now_ms = max(
                window_a.window_end_ms,
                window_b.window_end_ms,
            )
            window_start_ms = now_ms - window_seconds * 1000

            samples_a = [
                s for s in window_a.samples
                if s.aggregated_at_ms >= window_start_ms
            ]
            samples_b = [
                s for s in window_b.samples
                if s.aggregated_at_ms >= window_start_ms
            ]

            if len(samples_a) < 30 or len(samples_b) < 30:
                return None

            # Align samples by timestamp (nearest neighbor within 200ms)
            aligned_returns_a = []
            aligned_returns_b = []

            for sa in samples_a:
                # Find nearest sample in B within 200ms
                closest_sb = None
                min_diff = 200  # 200ms tolerance
                for sb in samples_b:
                    diff = abs(sa.aggregated_at_ms - sb.aggregated_at_ms)
                    if diff < min_diff:
                        closest_sb = sb
                        min_diff = diff

                if closest_sb:
                    # Compute log returns if we have historical data
                    for i, sample in enumerate(samples_a):
                        if i > 0 and sample.aggregated_at_ms == sa.aggregated_at_ms:
                            prev = samples_a[i - 1]
                            if prev.consensus_price > 0 and sa.consensus_price > 0:
                                ret_a = float(math.log(sa.consensus_price / prev.consensus_price))
                                aligned_returns_a.append(ret_a)

                    for i, sample in enumerate(samples_b):
                        if i > 0 and sample.aggregated_at_ms == closest_sb.aggregated_at_ms:
                            prev = samples_b[i - 1]
                            if prev.consensus_price > 0 and closest_sb.consensus_price > 0:
                                ret_b = float(
                                    math.log(closest_sb.consensus_price / prev.consensus_price)
                                )
                                aligned_returns_b.append(ret_b)

            if len(aligned_returns_a) < 30 or len(aligned_returns_b) < 30:
                return None

            # Compute correlation
            try:
                corr_matrix = np.corrcoef(
                    aligned_returns_a[:len(aligned_returns_b)],
                    aligned_returns_b[:len(aligned_returns_a)],
                )
                correlation = float(corr_matrix[0, 1])
                return correlation
            except Exception as e:
                _logger.warning("CORRELATION_COMPUTE_ERROR: %s", str(e))
                return None

    def get_spread_momentum(
        self, symbol: str, dex_a: str, dex_b: str, window_seconds: int = 5
    ) -> float:
        """
        Compute rate of change of price spread over recent window.
        
        Used by inference feature extractor as spread_momentum_5s.
        
        Args:
            symbol: Trading pair
            dex_a: First DEX identifier
            dex_b: Second DEX identifier
            window_seconds: Time window (default 5s)
            
        Returns:
            Rate of change of spread (could be positive or negative)
        """
        with self._lock:
            window = self.windows.get(symbol)
            if not window or len(window.samples) < 2:
                return 0.0

            now_ms = window.window_end_ms
            window_start_ms = now_ms - window_seconds * 1000

            samples = [
                s for s in window.samples
                if s.aggregated_at_ms >= window_start_ms
            ]

            if len(samples) < 2:
                return 0.0

            # Extract spreads from samples (using bid-ask as proxy)
            spreads = []
            timestamps = []

            for sample in samples:
                if sample.bid_price > 0 and sample.ask_price > 0:
                    spread_bps = (
                        (sample.ask_price - sample.bid_price)
                        / sample.bid_price
                        * 10000
                    )
                    spreads.append(float(spread_bps))
                    timestamps.append(sample.aggregated_at_ms)

            if len(spreads) < 2:
                return 0.0

            # Compute linear regression: spread = a + b*time
            times = [(t - timestamps[0]) / 1000.0 for t in timestamps]
            try:
                coeffs = np.polyfit(times, spreads, 1)
                momentum = coeffs[0]  # Slope
                return momentum
            except Exception as e:
                _logger.debug("SPREAD_MOMENTUM_ERROR: %s", str(e))
                return 0.0

    def get_freshness_report(self) -> dict[str, FreshnessReport]:
        """
        Generate per-symbol freshness metrics for monitoring dashboard.
        
        Returns:
            Dict mapping symbol to FreshnessReport
        """
        reports = {}

        with self._lock:
            for symbol, window in self.windows.items():
                if not window.samples:
                    reports[symbol] = FreshnessReport(
                        total_samples=0,
                        violation_count=0,
                        violation_rate_pct=0.0,
                        avg_staleness_ms=0.0,
                        p95_staleness_ms=0.0,
                        sources_ranked_by_freshness=[],
                        data_gaps=[],
                        recommendation="No data recorded yet",
                    )
                    continue

                staleness_values = [
                    s.oldest_source_staleness_ms for s in window.samples
                ]

                violation_count = sum(
                    1 for s in staleness_values
                    if s > 500  # MAX_STALENESS_MS
                )

                avg_staleness = sum(staleness_values) / len(staleness_values)
                p95_staleness = float(np.percentile(staleness_values, 95))

                # Rank sources by freshness
                all_sources_freshness = []
                for source in set(
                    s for state in window.samples
                    for s in state.sources_used
                ):
                    avg_for_source = np.mean(
                        [
                            s.oldest_source_staleness_ms
                            for s in window.samples
                            if source in s.sources_used
                        ]
                    )
                    all_sources_freshness.append((source, float(avg_for_source)))

                all_sources_freshness.sort(key=lambda x: x[1])

                reports[symbol] = FreshnessReport(
                    total_samples=len(window.samples),
                    violation_count=violation_count,
                    violation_rate_pct=100.0
                    * violation_count
                    / len(window.samples),
                    avg_staleness_ms=avg_staleness,
                    p95_staleness_ms=p95_staleness,
                    sources_ranked_by_freshness=all_sources_freshness,
                    data_gaps=[],
                    recommendation="System operating normally",
                )

        return reports


__all__ = ["MarketStateWindowStore"]
