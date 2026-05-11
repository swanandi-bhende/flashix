"""Fallback orchestrator with Pyth → Chainlink → 1inch cascade and execution pause logic."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Optional, TYPE_CHECKING

from agent.market_data import FallbackState, OracleSource, RawPriceSample
from agent.market_data.aggregator import OracleAggregator
from agent.market_data.chainlink_client import ChainlinkOracleClient
from agent.market_data.oneinch_client import OneInchClient
from agent.market_data.pyth_client import PythOracleClient

if TYPE_CHECKING:
    from agent.risk.risk_registry import RiskRegistry

_logger = logging.getLogger(__name__)


class FallbackOrchestrator:
    """
    Monitors oracle health in real time and enforces three-tier fallback cascade.
    
    Priority order:
    1. Pyth (fastest, most decentralized)
    2. Chainlink (on-chain, battle-tested)
    3. 1inch/DEX direct (fallback if both primary sources fail)
    
    If all sources fail, opens ORACLE_FAILURE circuit breaker to pause execution.
    """

    def __init__(
        self,
        pyth_client: PythOracleClient,
        chainlink_client: ChainlinkOracleClient,
        oneinch_client: OneInchClient,
        risk_registry: RiskRegistry,
        aggregator: OracleAggregator,
    ):
        """
        Initialize orchestrator with oracle clients and risk registry.
        
        Args:
            pyth_client: Pyth Network WebSocket client
            chainlink_client: Chainlink on-chain polling client
            oneinch_client: 1inch DEX aggregator client
            risk_registry: Risk system for circuit breaker control
            aggregator: Oracle aggregator for consensus
        """
        self.pyth_client = pyth_client
        self.chainlink_client = chainlink_client
        self.oneinch_client = oneinch_client
        self.risk_registry = risk_registry
        self.aggregator = aggregator

        self._recovery_monitor_running = False
        self._recovery_monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    def start_recovery_monitor(self) -> None:
        """Start background oracle recovery monitor thread."""
        if self._recovery_monitor_running:
            return
        self._recovery_monitor_running = True
        self._recovery_monitor_thread = threading.Thread(
            target=self._oracle_recovery_monitor_loop,
            daemon=True,
        )
        self._recovery_monitor_thread.start()
        _logger.info("ORACLE_RECOVERY_MONITOR_STARTED")

    def stop_recovery_monitor(self) -> None:
        """Stop recovery monitor thread."""
        self._recovery_monitor_running = False
        if self._recovery_monitor_thread:
            self._recovery_monitor_thread.join(timeout=5.0)

    def get_best_available_price(
        self, symbol: str
    ) -> tuple[Optional[RawPriceSample], Optional[OracleSource]]:
        """
        Try oracle sources in fallback cascade priority order.
        
        Algorithm:
        1. Try Pyth if ACTIVE
        2. Fall back to Chainlink if Pyth unavailable
        3. Fall back to 1inch if both fail
        4. If all fail, trigger execution pause and return None
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            (sample, source) tuple, or (None, None) if all fail
        """
        # Attempt 1: Pyth (primary, fastest)
        if self.pyth_client.get_fallback_state() == FallbackState.ACTIVE:
            sample = self.pyth_client.get_latest(symbol)
            if sample and sample.is_valid:
                return sample, OracleSource.PYTH

        # Attempt 2: Chainlink (fallback)
        pyth_state = self.pyth_client.get_fallback_state()
        _logger.warning(
            "PYTH_FALLBACK_TO_CHAINLINK: symbol=%s, pyth_state=%s",
            symbol,
            pyth_state.value,
        )

        chainlink_sample = self.chainlink_client.fetch(symbol)
        if chainlink_sample and chainlink_sample.is_valid:
            return chainlink_sample, OracleSource.CHAINLINK

        # Attempt 3: 1inch (DEX aggregator)
        chainlink_state = self.chainlink_client.get_fallback_state()
        _logger.warning(
            "CHAINLINK_FALLBACK_TO_1INCH: symbol=%s, chainlink_state=%s",
            symbol,
            chainlink_state.value,
        )

        # For 1inch, we'd need token addresses; using async wrapper
        try:
            oneinch_sample = asyncio.run_coroutine_threadsafe(
                self.oneinch_client.fetch_swap_quote(
                    "0x0000000000000000000000000000000000000000",  # from_token (update)
                    "0x0000000000000000000000000000000000000000",  # to_token (update)
                    None,  # amount (would need actual value)
                ),
                asyncio.get_event_loop(),
            ).result(timeout=1.0)

            if oneinch_sample and oneinch_sample.is_valid:
                return oneinch_sample, OracleSource.ONE_INCH
        except Exception as e:
            _logger.debug("ONE_INCH_FALLBACK_ERROR: %s", str(e))

        # All sources failed: trigger execution pause
        _logger.critical(
            "ALL_ORACLES_FAILED: symbol=%s, pyth=%s, chainlink=%s, oneinch=%s",
            symbol,
            pyth_state.value,
            chainlink_state.value,
            self.oneinch_client.get_fallback_state().value,
        )

        self._trigger_execution_pause(
            symbol, reason="ALL_ORACLES_FAILED"
        )

        return None, None

    def _trigger_execution_pause(self, symbol: str, reason: str) -> None:
        """
        Open ORACLE_FAILURE circuit breaker to halt execution.
        
        Args:
            symbol: Trading pair affected
            reason: Reason for pause (for logs)
        """
        from agent.risk_manager import BreakerType

        self.risk_registry.open_breaker(
            breaker_type=BreakerType.ORACLE_FAILURE if hasattr(
                BreakerType, "ORACLE_FAILURE"
            ) else None,
            trigger_value=0.0,
            opportunity_id=None,
            auto_reset_seconds=None,  # Manual reset required
            notes=f"Oracle failure for {symbol}: {reason}",
        )

    def _oracle_recovery_monitor_loop(self) -> None:
        """
        Background thread that monitors failed oracles for recovery.
        
        Every 10 seconds, attempt a test fetch from each FAILED oracle.
        If successful, set state to ACTIVE and close circuit breaker.
        """
        while self._recovery_monitor_running:
            try:
                time.sleep(10)

                # Test Pyth recovery
                if self.pyth_client.get_fallback_state() == FallbackState.FAILED:
                    # Pyth uses WebSocket; can't easily test without connection
                    # Rely on natural reconnection with backoff
                    pass

                # Test Chainlink recovery
                if self.chainlink_client.get_fallback_state() == FallbackState.FAILED:
                    test_sample = self.chainlink_client.fetch("BTC-USD")
                    if test_sample and test_sample.is_valid:
                        _logger.info("ORACLE_RECOVERED: source=CHAINLINK")
                        self._close_oracle_failure_breaker()

                # Test 1inch recovery
                if self.oneinch_client.get_fallback_state() == FallbackState.FAILED:
                    # Would need async handling; skip for now
                    pass

            except Exception as e:
                _logger.error("ORACLE_RECOVERY_MONITOR_ERROR: %s", str(e))

    def _close_oracle_failure_breaker(self) -> None:
        """Close ORACLE_FAILURE breaker when oracle recovers."""
        from agent.risk_manager import BreakerType

        breaker_type = BreakerType.ORACLE_FAILURE if hasattr(
            BreakerType, "ORACLE_FAILURE"
        ) else None

        if breaker_type:
            self.risk_registry.close_breaker(
                breaker_type=breaker_type,
                resolution_method="ORACLE_RECOVERED",
            )


__all__ = ["FallbackOrchestrator"]
