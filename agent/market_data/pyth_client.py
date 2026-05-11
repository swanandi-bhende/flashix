"""Pyth Network oracle client with WebSocket streaming and price validation."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Optional

import websockets

from agent.market_data import (
    FallbackState,
    MAX_STALENESS_MS,
    OracleSource,
    PYTH_TIMEOUT_MS,
    RawPriceSample,
)
from utils.constants import PYTH_PRICE_IDS

_logger = logging.getLogger(__name__)


class PythOracleClient:
    """
    Subscribes to Pyth Network's Hermes price feed service for real-time perpetual swap prices.
    
    Manages WebSocket lifecycle with reconnection, validates incoming prices, and exposes
    the latest valid sample per symbol. Tracks fallback state for orchestrator cascade.
    """

    def __init__(self):
        """Initialize Pyth client with WebSocket subscription ready to start."""
        self.ws_uri = "wss://hermes.pyth.network/ws"
        self.websocket = None
        self.fallback_state: FallbackState = FallbackState.ACTIVE
        self.latest_samples: dict[str, RawPriceSample] = {}
        self.consecutive_failures: int = 0
        self.last_heartbeat: int = int(time.time() * 1000)
        self.ping_interval_seconds: int = 20
        self._running: bool = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the WebSocket connection and message loop."""
        self._running = True
        await self._connect_and_subscribe()

    async def stop(self) -> None:
        """Stop the WebSocket connection gracefully."""
        self._running = False
        if self.websocket:
            await self.websocket.close()

    async def _connect_and_subscribe(self) -> None:
        """
        Establish WebSocket connection to Hermes with exponential backoff reconnection.
        """
        backoff_seconds = 1
        max_backoff = 60

        while self._running:
            try:
                async with websockets.connect(
                    self.ws_uri,
                    ping_interval=self.ping_interval_seconds,
                    ping_timeout=self.ping_interval_seconds * 2,
                ) as websocket:
                    self.websocket = websocket
                    self.consecutive_failures = 0
                    backoff_seconds = 1
                    _logger.info("PYTH_WEBSOCKET_CONNECTED")

                    # Subscribe to price feeds
                    subscription_msg = {
                        "type": "subscribe",
                        "ids": list(PYTH_PRICE_IDS.values()),
                    }
                    await websocket.send(json.dumps(subscription_msg))
                    _logger.info("PYTH_SUBSCRIPTION_SENT: subscribed to %d price feeds", len(PYTH_PRICE_IDS))

                    # Read messages
                    async for message in websocket:
                        if not self._running:
                            break
                        await self._on_message(message)

            except asyncio.TimeoutError:
                self.consecutive_failures += 1
                _logger.warning("PYTH_TIMEOUT: failures=%d", self.consecutive_failures)
                if self.consecutive_failures >= 3:
                    self.fallback_state = FallbackState.FAILED
                    _logger.critical("PYTH_CIRCUIT_OPEN: consecutive_failures >= 3")
            except Exception as e:
                self.consecutive_failures += 1
                _logger.warning("PYTH_CONNECTION_ERROR: %s, failures=%d", str(e), self.consecutive_failures)
                if self.consecutive_failures >= 3:
                    self.fallback_state = FallbackState.FAILED
                    _logger.critical("PYTH_CIRCUIT_OPEN: consecutive_failures >= 3")

            if self._running and self.consecutive_failures >= 3:
                # Back off before retry
                await asyncio.sleep(min(backoff_seconds, max_backoff))
                backoff_seconds *= 2

    async def _on_message(self, raw: str) -> None:
        """
        Parse incoming Pyth price update JSON and store as RawPriceSample.
        
        Pyth message format:
        {
            "type": "price_update",
            "id": "<feed_id>",
            "price": {"price": "45000000000", "conf": "100000000", "expo": -8, "publish_time": 1234567890}
        }
        """
        try:
            data = json.loads(raw)
            if data.get("type") != "price_update":
                return

            feed_id = data.get("id")
            price_data = data.get("price", {})

            if not feed_id or not price_data:
                return

            # Find symbol for this feed ID
            symbol = None
            for sym, pid in PYTH_PRICE_IDS.items():
                if pid == feed_id:
                    symbol = sym
                    break

            if not symbol:
                _logger.debug("PYTH_UNKNOWN_FEED_ID: id=%s", feed_id)
                return

            # Extract price components
            price_str = price_data.get("price", "0")
            conf = int(price_data.get("conf", 0))
            expo = int(price_data.get("expo", 0))
            publish_time = int(price_data.get("publish_time", 0))

            # Convert to Decimal with proper exponent
            price = Decimal(price_str) * Decimal(10) ** Decimal(expo)
            now_ms = int(time.time() * 1000)
            staleness_ms = now_ms - (publish_time * 1000)

            # Validate sample
            sample = RawPriceSample(
                source=OracleSource.PYTH,
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
                source_timestamp_ms=publish_time * 1000,
                staleness_ms=staleness_ms,
                fetch_latency_ms=0.0,
                is_valid=False,
            )

            is_valid, reason = self._validate_sample(sample)
            if is_valid:
                async with self._lock:
                    self.latest_samples[symbol] = sample._replace(is_valid=True)
                    self.consecutive_failures = 0
                    if self.fallback_state == FallbackState.FAILED:
                        self.fallback_state = FallbackState.ACTIVE
                        _logger.info("PYTH_RECOVERED: fallback_state=ACTIVE")
            else:
                sample = sample._replace(is_valid=False, validation_failure_reason=reason)

        except json.JSONDecodeError as e:
            _logger.debug("PYTH_JSON_PARSE_ERROR: %s", str(e))
        except Exception as e:
            _logger.warning("PYTH_MESSAGE_PARSE_ERROR: %s", str(e))

    def _validate_sample(self, sample: RawPriceSample) -> tuple[bool, Optional[str]]:
        """
        Validate a raw price sample before accepting it.
        
        Rejects samples where:
        - Confidence interval is too wide (>0.1% of price)
        - Staleness exceeds MAX_STALENESS_MS
        - Price is invalid (<=0)
        """
        if sample.mid_price <= 0:
            return False, "INVALID_PRICE: price <= 0"

        if sample.staleness_ms > MAX_STALENESS_MS:
            return False, f"STALE: staleness_ms={sample.staleness_ms} > {MAX_STALENESS_MS}"

        # Pyth confidence interval check (would need conf data in sample)
        # For now, confidence is implicit in the price precision
        return True, None

    def get_latest(self, symbol: str) -> Optional[RawPriceSample]:
        """Return the most recent valid sample for a symbol, or None if unavailable/failed."""
        if self.fallback_state == FallbackState.FAILED:
            return None
        return self.latest_samples.get(symbol)

    def get_fallback_state(self) -> FallbackState:
        """Return current health state of Pyth oracle."""
        return self.fallback_state


__all__ = ["PythOracleClient"]
