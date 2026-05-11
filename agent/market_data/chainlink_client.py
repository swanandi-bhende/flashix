"""Chainlink oracle client with on-chain price feed polling and round validation."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Optional

from web3 import Web3

from agent.market_data import (
    CHAINLINK_TIMEOUT_MS,
    FallbackState,
    MAX_STALENESS_MS,
    OracleSource,
    RawPriceSample,
)
from utils.constants import CHAINLINK_FEED_ADDRESSES

_logger = logging.getLogger(__name__)


AGGREGATOR_V3_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


class ChainlinkOracleClient:
    """
    Reads prices from Chainlink AggregatorV3Interface contracts via eth_call.
    
    Polls feeds every 2 seconds, validates round data freshness, and maintains
    circuit breaker state for fallback orchestrator.
    """

    def __init__(self, rpc_endpoint: str):
        """
        Initialize Chainlink client.
        
        Args:
            rpc_endpoint: Web3 RPC endpoint (can be different from trading RPC to avoid rate-limiting)
        """
        self.web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
        self.rpc_endpoint = rpc_endpoint
        self.fallback_state: FallbackState = FallbackState.ACTIVE
        self.latest_samples: dict[str, RawPriceSample] = {}
        self.consecutive_failures: int = 0
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self.poll_interval_seconds: int = 2

    def start_monitoring(self) -> None:
        """Start background polling thread."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._monitor_thread.start()
        _logger.info("CHAINLINK_MONITOR_STARTED")

    def stop_monitoring(self) -> None:
        """Stop background polling thread."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

    def _polling_loop(self) -> None:
        """Background thread: poll all feed addresses every 2 seconds."""
        while self._running:
            try:
                self._poll_all_feeds()
            except Exception as e:
                _logger.error("CHAINLINK_POLLING_ERROR: %s", str(e))
            time.sleep(self.poll_interval_seconds)

    def _poll_all_feeds(self) -> None:
        """Poll all configured Chainlink feeds concurrently."""
        if not CHAINLINK_FEED_ADDRESSES:
            return

        with ThreadPoolExecutor(max_workers=min(5, len(CHAINLINK_FEED_ADDRESSES))) as executor:
            futures = {
                executor.submit(self.fetch, symbol): symbol for symbol in CHAINLINK_FEED_ADDRESSES.keys()
            }
            for future in as_completed(futures, timeout=CHAINLINK_TIMEOUT_MS / 1000.0 + 1):
                try:
                    future.result()
                except Exception as e:
                    _logger.debug("CHAINLINK_FETCH_ERROR: %s", str(e))

    def fetch(self, symbol: str) -> Optional[RawPriceSample]:
        """
        Fetch the latest price for a symbol from its Chainlink feed contract.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            
        Returns:
            RawPriceSample if valid, None on error
        """
        feed_address = CHAINLINK_FEED_ADDRESSES.get(symbol)
        if not feed_address:
            _logger.debug("CHAINLINK_NO_FEED: symbol=%s", symbol)
            return None

        try:
            contract = self.web3.eth.contract(address=feed_address, abi=AGGREGATOR_V3_ABI)

            # Get decimals
            decimals = contract.functions.decimals().call()

            # Get latest round data
            round_data = contract.functions.latestRoundData().call()
            round_id, answer, started_at, updated_at, answered_in_round = round_data

            # Validate round data
            if answered_in_round < round_id:
                self.consecutive_failures += 1
                _logger.warning(
                    "CHAINLINK_STALE_ROUND: symbol=%s, answered_in_round=%d < round_id=%d",
                    symbol,
                    answered_in_round,
                    round_id,
                )
                if self.consecutive_failures >= 3:
                    self.fallback_state = FallbackState.FAILED
                    _logger.critical("CHAINLINK_CIRCUIT_OPEN: consecutive_failures >= 3")
                return None

            if answer <= 0:
                _logger.warning("CHAINLINK_INVALID_PRICE: symbol=%s, answer=%d", symbol, answer)
                return None

            # Check if data is fresh (updated in last hour)
            now = int(time.time())
            if updated_at < now - 3600:
                self.consecutive_failures += 1
                _logger.warning(
                    "CHAINLINK_STALE_DATA: symbol=%s, updated_at=%d is >1h old",
                    symbol,
                    updated_at,
                )
                if self.consecutive_failures >= 3:
                    self.fallback_state = FallbackState.FAILED
                    _logger.critical("CHAINLINK_CIRCUIT_OPEN: consecutive_failures >= 3")
                return None

            # Convert price to Decimal
            price = Decimal(answer) / Decimal(10) ** decimals
            now_ms = int(time.time() * 1000)
            staleness_ms = (now - updated_at) * 1000

            sample = RawPriceSample(
                source=OracleSource.CHAINLINK,
                symbol=symbol,
                mark_price=price,
                index_price=price,
                funding_rate=Decimal("0"),
                funding_rate_annualized=Decimal("0"),
                collateral_ratio=Decimal("1.0"),
                bid_price=price,
                ask_price=price,
                mid_price=price,
                spread_bps=0.0,
                fetched_at_ms=now_ms,
                source_timestamp_ms=updated_at * 1000,
                staleness_ms=staleness_ms,
                fetch_latency_ms=0.0,
                is_valid=staleness_ms <= MAX_STALENESS_MS,
            )

            with self._lock:
                self.latest_samples[symbol] = sample
                self.consecutive_failures = 0
                if self.fallback_state == FallbackState.FAILED:
                    self.fallback_state = FallbackState.ACTIVE
                    _logger.info("CHAINLINK_RECOVERED: fallback_state=ACTIVE")

            return sample

        except Exception as e:
            self.consecutive_failures += 1
            _logger.warning("CHAINLINK_FETCH_ERROR: symbol=%s, error=%s, failures=%d", symbol, str(e), self.consecutive_failures)
            if self.consecutive_failures >= 3:
                self.fallback_state = FallbackState.FAILED
                _logger.critical("CHAINLINK_CIRCUIT_OPEN: consecutive_failures >= 3")
            return None

    def get_latest(self, symbol: str) -> Optional[RawPriceSample]:
        """Return the most recent valid sample for a symbol."""
        with self._lock:
            return self.latest_samples.get(symbol)

    def get_fallback_state(self) -> FallbackState:
        """Return current health state of Chainlink oracle."""
        return self.fallback_state


__all__ = ["ChainlinkOracleClient"]
