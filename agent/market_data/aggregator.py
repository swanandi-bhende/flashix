"""Oracle aggregator that merges inputs from all sources and detects manipulation."""

from __future__ import annotations

import logging
import statistics
from decimal import Decimal
from typing import Optional

from agent.market_data import (
    AggregatedMarketState,
    DataQualityLevel,
    MANIPULATION_DETECTION_THRESHOLD_PCT,
    MIN_SOURCES_FOR_EXECUTION,
    OracleSource,
    RawPriceSample,
)

_logger = logging.getLogger(__name__)


class OracleAggregator:
    """
    Central intelligence that merges raw samples from Pyth, Chainlink, and 1inch
    into a single trusted consensus market state using statistical aggregation.
    
    Detects manipulation via outlier detection and removes suspicious sources
    from the consensus calculation.
    """

    def aggregate(
        self, symbol: str, raw_samples: list[RawPriceSample]
    ) -> AggregatedMarketState:
        """
        Produce a consensus AggregatedMarketState from multiple oracle samples.
        
        Algorithm:
        1. Filter to valid, fresh samples only
        2. If no valid samples, return UNAVAILABLE quality state
        3. Compute median price as consensus (robust to outliers)
        4. Detect and remove manipulation (>0.5% deviation from consensus)
        5. Recompute consensus without outliers
        6. Classify data quality based on number of sources
        
        Args:
            symbol: Trading pair symbol
            raw_samples: List of raw price samples from various oracles
            
        Returns:
            AggregatedMarketState with consensus price and quality metrics
        """
        import time

        now_ms = int(time.time() * 1000)

        # Step 1: Filter valid, fresh samples
        valid_samples = [
            s for s in raw_samples
            if s.is_valid and s.staleness_ms <= 500  # MAX_STALENESS_MS
        ]

        sources_tried = set(s.source for s in raw_samples)
        sources_failed = set(s.source for s in raw_samples) - set(s.source for s in valid_samples)

        # Step 2: Check for unavailability
        if not valid_samples:
            _logger.warning(
                "ORACLE_AGGREGATION_UNAVAILABLE: symbol=%s, sources_tried=%s",
                symbol,
                [s.value for s in sources_tried],
            )
            return AggregatedMarketState(
                symbol=symbol,
                consensus_price=Decimal("0"),
                price_std_dev=Decimal("0"),
                max_deviation_pct=0.0,
                funding_rate_consensus=Decimal("0"),
                collateral_ratio_consensus=Decimal("0"),
                sources_used=[],
                sources_failed=list(sources_failed),
                data_quality=DataQualityLevel.UNAVAILABLE,
                aggregated_at_ms=now_ms,
                oldest_source_staleness_ms=0,
            )

        # Step 3: Compute initial consensus (median)
        prices = [s.mid_price for s in valid_samples]
        consensus_price = Decimal(str(statistics.median(prices)))

        # Step 4: Detect manipulation (outliers)
        outlier_samples = []
        trustworthy_samples = []

        for sample in valid_samples:
            if consensus_price > 0:
                deviation_pct = (
                    abs(sample.mid_price - consensus_price) / consensus_price * 100
                )
            else:
                deviation_pct = 0.0

            if deviation_pct > MANIPULATION_DETECTION_THRESHOLD_PCT:
                outlier_samples.append((sample, deviation_pct))
                _logger.warning(
                    "ORACLE_DEVIATION_ALERT: symbol=%s, source=%s, deviation=%.3f%%, "
                    "consensus_price=%s, sample_price=%s",
                    symbol,
                    sample.source.value,
                    deviation_pct,
                    consensus_price,
                    sample.mid_price,
                )
            else:
                trustworthy_samples.append(sample)

        sources_failed = set(sources_failed)
        sources_failed.update(sample.source for sample, _ in outlier_samples)

        # Step 5: Recompute consensus without outliers
        if trustworthy_samples:
            prices = [s.mid_price for s in trustworthy_samples]
            consensus_price = Decimal(str(statistics.median(prices)))

            # Compute price standard deviation
            if len(prices) > 1:
                price_std_dev = Decimal(str(statistics.stdev(prices)))
            else:
                price_std_dev = Decimal("0")

            # Compute max deviation for the trustworthy set
            max_deviation_pct = 0.0
            for sample in trustworthy_samples:
                if consensus_price > 0:
                    deviation_pct = (
                        abs(sample.mid_price - consensus_price) / consensus_price * 100
                    )
                else:
                    deviation_pct = 0.0
                max_deviation_pct = max(max_deviation_pct, deviation_pct)

            sources_used = [s.source for s in trustworthy_samples]
        else:
            # All samples were outliers; fall back to original consensus with all data
            if len(prices) > 1:
                price_std_dev = Decimal(str(statistics.stdev(prices)))
            else:
                price_std_dev = Decimal("0")

            max_deviation_pct = 0.0
            for sample in valid_samples:
                if consensus_price > 0:
                    deviation_pct = (
                        abs(sample.mid_price - consensus_price) / consensus_price * 100
                    )
                else:
                    deviation_pct = 0.0
                max_deviation_pct = max(max_deviation_pct, deviation_pct)

            sources_used = [s.source for s in valid_samples]

        # Step 6: Classify data quality
        num_sources = len(sources_used)
        if num_sources >= 3:
            data_quality = DataQualityLevel.HIGH
        elif num_sources == 2:
            data_quality = DataQualityLevel.MEDIUM
        elif num_sources == 1:
            data_quality = DataQualityLevel.LOW
        else:
            data_quality = DataQualityLevel.UNAVAILABLE

        # Compute funding rate consensus
        valid_funding_rates = [
            s.funding_rate for s in valid_samples
            if s.funding_rate is not None
        ]
        if valid_funding_rates:
            funding_rate_consensus = Decimal(
                str(statistics.median(valid_funding_rates))
            )
        else:
            funding_rate_consensus = Decimal("0")

        # Compute collateral ratio consensus
        valid_collateral_ratios = [
            s.collateral_ratio for s in valid_samples
            if s.collateral_ratio is not None
        ]
        if valid_collateral_ratios:
            collateral_ratio_consensus = Decimal(
                str(statistics.median(valid_collateral_ratios))
            )
        else:
            collateral_ratio_consensus = Decimal("1.0")

        # Compute oldest source staleness
        oldest_staleness = max(
            (s.staleness_ms for s in valid_samples),
            default=0,
        )

        return AggregatedMarketState(
            symbol=symbol,
            consensus_price=consensus_price,
            price_std_dev=price_std_dev,
            max_deviation_pct=max_deviation_pct,
            funding_rate_consensus=funding_rate_consensus,
            collateral_ratio_consensus=collateral_ratio_consensus,
            sources_used=sources_used,
            sources_failed=list(sources_failed),
            data_quality=data_quality,
            aggregated_at_ms=now_ms,
            oldest_source_staleness_ms=oldest_staleness,
        )

    def is_safe_to_execute(
        self, state: AggregatedMarketState
    ) -> tuple[bool, str]:
        """
        Determine if aggregated state quality is sufficient for execution.
        
        Returns:
            (allowed, reason) tuple
            - UNAVAILABLE: No valid sources
            - SINGLE_SOURCE_RISK: Only 1 source (too risky)
            - OK: Safe to execute (2+ sources, HIGH or MEDIUM quality)
        """
        if state.data_quality == DataQualityLevel.UNAVAILABLE:
            return False, "UNAVAILABLE"

        if state.data_quality == DataQualityLevel.LOW:
            return False, "SINGLE_SOURCE_RISK"

        # MEDIUM or HIGH quality is safe
        return True, "OK"


__all__ = ["OracleAggregator"]
