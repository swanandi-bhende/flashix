"""Integration tests for the complete market data pipeline."""

from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from agent.market_data import (
    AggregatedMarketState,
    DataQualityLevel,
    FallbackState,
    OracleSource,
    RawPriceSample,
)
from agent.market_data.aggregator import OracleAggregator
from agent.market_data.chainlink_client import ChainlinkOracleClient
from agent.market_data.freshness_monitor import FreshnessMonitor
from agent.market_data.oneinch_client import OneInchClient
from agent.market_data.pyth_client import PythOracleClient
from agent.market_data.window_store import MarketStateWindowStore


class TestOracleAggregation:
    """Test oracle aggregation and consensus logic."""

    def test_pyth_aggregation_high_quality(self):
        """
        Verify HIGH data quality when three oracle sources agree within 0.05%.
        
        Aggregator should produce HIGH quality consensus with prices within 0.05%.
        """
        aggregator = OracleAggregator()
        symbol = "BTC-USD-PERP"
        base_price = Decimal("45000.00")

        # Three samples within 0.05% of each other
        samples = [
            RawPriceSample(
                source=OracleSource.PYTH,
                symbol=symbol,
                mark_price=base_price,
                index_price=base_price,
                funding_rate=Decimal("0.0001"),
                funding_rate_annualized=Decimal("0.36"),
                collateral_ratio=Decimal("2.5"),
                bid_price=base_price - Decimal("1"),
                ask_price=base_price + Decimal("1"),
                mid_price=base_price,
                spread_bps=2.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=10,
                fetch_latency_ms=50.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.CHAINLINK,
                symbol=symbol,
                mark_price=base_price + Decimal("20"),  # +0.044%
                index_price=base_price + Decimal("20"),
                funding_rate=Decimal("0.00011"),
                funding_rate_annualized=Decimal("0.37"),
                collateral_ratio=Decimal("2.51"),
                bid_price=base_price + Decimal("19"),
                ask_price=base_price + Decimal("21"),
                mid_price=base_price + Decimal("20"),
                spread_bps=2.2,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=15,
                fetch_latency_ms=80.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.ONE_INCH,
                symbol=symbol,
                mark_price=base_price - Decimal("15"),  # -0.033%
                index_price=base_price - Decimal("15"),
                funding_rate=Decimal("0.00009"),
                funding_rate_annualized=Decimal("0.35"),
                collateral_ratio=Decimal("2.49"),
                bid_price=base_price - Decimal("16"),
                ask_price=base_price - Decimal("14"),
                mid_price=base_price - Decimal("15"),
                spread_bps=2.1,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=12,
                fetch_latency_ms=60.0,
                is_valid=True,
            ),
        ]

        aggregated = aggregator.aggregate(symbol, samples)

        assert aggregated.data_quality == DataQualityLevel.HIGH
        assert aggregated.consensus_price == Decimal("45000")  # Median
        assert len(aggregated.sources_used) == 3
        assert aggregated.max_deviation_pct < 0.1

    def test_manipulation_detection_excludes_outlier(self):
        """
        Verify outlier sources are excluded from consensus and flagged.
        
        When one source deviates 0.8% from others, it should be excluded
        and consensus recomputed without it.
        """
        aggregator = OracleAggregator()
        symbol = "ETH-USD-PERP"
        base_price = Decimal("2250.00")

        samples = [
            RawPriceSample(
                source=OracleSource.PYTH,
                symbol=symbol,
                mark_price=base_price,
                index_price=base_price,
                funding_rate=Decimal("0.0"),
                funding_rate_annualized=Decimal("0.0"),
                collateral_ratio=Decimal("1.0"),
                bid_price=base_price,
                ask_price=base_price,
                mid_price=base_price,
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=10,
                fetch_latency_ms=50.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.CHAINLINK,
                symbol=symbol,
                mark_price=base_price + Decimal("5"),  # +0.22%
                index_price=base_price + Decimal("5"),
                funding_rate=Decimal("0.0"),
                funding_rate_annualized=Decimal("0.0"),
                collateral_ratio=Decimal("1.0"),
                bid_price=base_price + Decimal("5"),
                ask_price=base_price + Decimal("5"),
                mid_price=base_price + Decimal("5"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=15,
                fetch_latency_ms=80.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.ONE_INCH,
                symbol=symbol,
                mark_price=base_price + Decimal("20"),  # +0.89% OUTLIER
                index_price=base_price + Decimal("20"),
                funding_rate=Decimal("0.0"),
                funding_rate_annualized=Decimal("0.0"),
                collateral_ratio=Decimal("1.0"),
                bid_price=base_price + Decimal("20"),
                ask_price=base_price + Decimal("20"),
                mid_price=base_price + Decimal("20"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=12,
                fetch_latency_ms=60.0,
                is_valid=True,
            ),
        ]

        aggregated = aggregator.aggregate(symbol, samples)

        # ONE_INCH should be flagged as failed (outlier)
        assert OracleSource.ONE_INCH in aggregated.sources_failed
        # Consensus should be median of remaining two: (2250 + 2255) / 2 = 2252.5
        assert aggregated.consensus_price == Decimal("2252.5")
        assert len(aggregated.sources_used) == 2

    def test_chainlink_fallback_activates_on_pyth_failure(self):
        """
        Verify fallback cascade: when Pyth is FAILED, cascade to Chainlink.
        """
        # Create mock clients
        pyth_client = MagicMock(spec=PythOracleClient)
        chainlink_client = MagicMock(spec=ChainlinkOracleClient)
        oneinch_client = MagicMock(spec=OneInchClient)
        risk_registry = MagicMock()
        aggregator = OracleAggregator()

        from agent.market_data.fallback_orchestrator import FallbackOrchestrator

        orchestrator = FallbackOrchestrator(
            pyth_client=pyth_client,
            chainlink_client=chainlink_client,
            oneinch_client=oneinch_client,
            risk_registry=risk_registry,
            aggregator=aggregator,
        )

        # Set up Pyth as FAILED
        pyth_client.get_fallback_state.return_value = FallbackState.FAILED
        pyth_client.get_latest.return_value = None

        # Set up Chainlink to return a valid sample
        sample = RawPriceSample(
            source=OracleSource.CHAINLINK,
            symbol="BTC-USD-PERP",
            mark_price=Decimal("45000"),
            index_price=Decimal("45000"),
            funding_rate=Decimal("0"),
            funding_rate_annualized=Decimal("0"),
            collateral_ratio=Decimal("1"),
            bid_price=Decimal("45000"),
            ask_price=Decimal("45000"),
            mid_price=Decimal("45000"),
            spread_bps=0.0,
            fetched_at_ms=int(time.time() * 1000),
            source_timestamp_ms=int(time.time() * 1000),
            staleness_ms=10,
            fetch_latency_ms=100.0,
            is_valid=True,
        )
        chainlink_client.fetch.return_value = sample
        chainlink_client.get_fallback_state.return_value = FallbackState.ACTIVE

        # Get best available price
        result_sample, source = orchestrator.get_best_available_price("BTC-USD-PERP")

        # Should return Chainlink sample
        assert result_sample == sample
        assert source == OracleSource.CHAINLINK

    def test_sliding_window_evicts_old_samples(self):
        """
        Verify sliding window evicts samples beyond 1000-sample limit.
        """
        window_store = MarketStateWindowStore(["BTC-USD-PERP"])

        # Insert 1001 samples
        for i in range(1001):
            state = AggregatedMarketState(
                symbol="BTC-USD-PERP",
                consensus_price=Decimal("45000") + Decimal(i),
                price_std_dev=Decimal("10"),
                max_deviation_pct=0.1,
                funding_rate_consensus=Decimal("0.0001"),
                collateral_ratio_consensus=Decimal("2.5"),
                sources_used=[OracleSource.PYTH],
                sources_failed=[],
                data_quality=DataQualityLevel.HIGH,
                aggregated_at_ms=int(time.time() * 1000) + i * 1000,
                oldest_source_staleness_ms=10,
            )
            window_store.record(state)

        # Should have exactly 1000 samples (maxlen)
        assert len(window_store.windows["BTC-USD-PERP"].samples) == 1000

    def test_staleness_violation_logged(self):
        """
        Verify staleness violations are recorded in the freshness database.
        """
        freshness_monitor = FreshnessMonitor(data_dir="/tmp/test_freshness")

        # Record a stale sample
        stale_sample = RawPriceSample(
            source=OracleSource.PYTH,
            symbol="BTC-USD-PERP",
            mark_price=Decimal("45000"),
            index_price=Decimal("45000"),
            funding_rate=Decimal("0"),
            funding_rate_annualized=Decimal("0"),
            collateral_ratio=Decimal("1"),
            bid_price=Decimal("45000"),
            ask_price=Decimal("45000"),
            mid_price=Decimal("45000"),
            spread_bps=0.0,
            fetched_at_ms=int(time.time() * 1000),
            source_timestamp_ms=int(time.time() * 1000) - 600,  # 600ms stale
            staleness_ms=600,  # > MAX_STALENESS_MS (500)
            fetch_latency_ms=50.0,
            is_valid=False,
        )

        freshness_monitor.record_sample_received(stale_sample)

        # Check that violation was logged
        report = freshness_monitor.generate_freshness_report(hours=1)
        assert report["total_violations"] > 0


class TestDataQualityClassification:
    """Test data quality classification logic."""

    def test_high_quality_with_three_sources(self):
        """HIGH quality = 3 sources agree."""
        aggregator = OracleAggregator()

        samples = [
            RawPriceSample(
                source=OracleSource.PYTH,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=10,
                fetch_latency_ms=50.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.CHAINLINK,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=15,
                fetch_latency_ms=80.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.ONE_INCH,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=12,
                fetch_latency_ms=60.0,
                is_valid=True,
            ),
        ]

        aggregated = aggregator.aggregate("BTC-USD-PERP", samples)
        assert aggregated.data_quality == DataQualityLevel.HIGH

    def test_medium_quality_with_two_sources(self):
        """MEDIUM quality = 2 sources."""
        aggregator = OracleAggregator()

        samples = [
            RawPriceSample(
                source=OracleSource.PYTH,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=10,
                fetch_latency_ms=50.0,
                is_valid=True,
            ),
            RawPriceSample(
                source=OracleSource.CHAINLINK,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=15,
                fetch_latency_ms=80.0,
                is_valid=True,
            ),
        ]

        aggregated = aggregator.aggregate("BTC-USD-PERP", samples)
        assert aggregated.data_quality == DataQualityLevel.MEDIUM

    def test_low_quality_with_one_source(self):
        """LOW quality = 1 source (risky, should not execute)."""
        aggregator = OracleAggregator()

        samples = [
            RawPriceSample(
                source=OracleSource.PYTH,
                symbol="BTC-USD-PERP",
                mark_price=Decimal("45000"),
                index_price=Decimal("45000"),
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1"),
                bid_price=Decimal("45000"),
                ask_price=Decimal("45000"),
                mid_price=Decimal("45000"),
                spread_bps=0.0,
                fetched_at_ms=int(time.time() * 1000),
                source_timestamp_ms=int(time.time() * 1000),
                staleness_ms=10,
                fetch_latency_ms=50.0,
                is_valid=True,
            ),
        ]

        aggregated = aggregator.aggregate("BTC-USD-PERP", samples)
        assert aggregated.data_quality == DataQualityLevel.LOW

        # Should not be safe to execute
        safe, reason = aggregator.is_safe_to_execute(aggregated)
        assert not safe
        assert reason == "SINGLE_SOURCE_RISK"

    def test_unavailable_quality_with_no_sources(self):
        """UNAVAILABLE = no valid sources."""
        aggregator = OracleAggregator()

        samples = []

        aggregated = aggregator.aggregate("BTC-USD-PERP", samples)
        assert aggregated.data_quality == DataQualityLevel.UNAVAILABLE

        # Should definitely not be safe to execute
        safe, reason = aggregator.is_safe_to_execute(aggregated)
        assert not safe
        assert reason == "UNAVAILABLE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
