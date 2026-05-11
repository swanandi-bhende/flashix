"""1inch API client for cross-DEX price aggregation and slippage estimation."""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Optional

import httpx

from agent.market_data import (
    FallbackState,
    ONE_INCH_TIMEOUT_MS,
    OracleSource,
    RawPriceSample,
    SlippageEstimate,
)
from utils.constants import ONE_INCH_TOKENS

_logger = logging.getLogger(__name__)


class OneInchClient:
    """
    Fetches real-time swap quotes from 1inch Aggregation Router API.
    
    Provides both pricing data and live slippage estimates that feed into cost calculations.
    Enforces rate limiting (1 RPS free tier) and timeout constraints.
    """

    def __init__(self, chain_id: int, api_key: Optional[str] = None):
        """
        Initialize 1inch client.
        
        Args:
            chain_id: Blockchain chain ID (e.g., 1 for Ethereum)
            api_key: Optional 1inch API key for higher rate limits
        """
        self.chain_id = chain_id
        self.api_key = api_key
        self.base_url = f"https://api.1inch.io/v5.2/{chain_id}"
        self.fallback_state: FallbackState = FallbackState.ACTIVE
        self.latest_samples: dict[str, RawPriceSample] = {}
        self._last_call_timestamp: float = 0.0
        self._call_semaphore = asyncio.Semaphore(1)
        self._lock = asyncio.Lock()
        self.min_interval_seconds: float = 1.0  # 1 RPS free tier

    async def fetch_swap_quote(
        self, from_token: str, to_token: str, amount_usdc: Decimal
    ) -> Optional[RawPriceSample]:
        """
        Fetch a swap quote from 1inch for pricing and slippage estimation.
        
        Args:
            from_token: Source token address
            to_token: Destination token address
            amount_usdc: Amount in USDC (will be converted to wei)
            
        Returns:
            RawPriceSample with pricing data, or None on error
        """
        async with self._call_semaphore:
            # Rate limit: minimum 1 second between calls
            now = time.time()
            if now < self._last_call_timestamp + self.min_interval_seconds:
                await asyncio.sleep(self._last_call_timestamp + self.min_interval_seconds - now)
            self._last_call_timestamp = time.time()

            try:
                # Convert amount to wei (assuming 6 decimals for USDC)
                amount_wei = int(amount_usdc * Decimal(10) ** 6)

                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                async with httpx.AsyncClient(timeout=ONE_INCH_TIMEOUT_MS / 1000.0) as client:
                    response = await client.get(
                        f"{self.base_url}/quote",
                        params={
                            "fromTokenAddress": from_token,
                            "toTokenAddress": to_token,
                            "amount": str(amount_wei),
                        },
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Extract pricing data
                    to_token_amount = Decimal(data.get("toTokenAmount", "0"))
                    estimated_gas = data.get("estimatedGas", 0)

                    # Compute effective price
                    if amount_usdc > 0:
                        effective_price = to_token_amount / amount_usdc
                    else:
                        effective_price = Decimal("0")

                    now_ms = int(time.time() * 1000)
                    symbol = f"{from_token}-{to_token}"

                    sample = RawPriceSample(
                        source=OracleSource.ONE_INCH,
                        symbol=symbol,
                        mark_price=effective_price,
                        index_price=effective_price,
                        funding_rate=Decimal("0"),
                        funding_rate_annualized=Decimal("0"),
                        collateral_ratio=Decimal("1.0"),
                        bid_price=effective_price,
                        ask_price=effective_price,
                        mid_price=effective_price,
                        spread_bps=0.0,
                        fetched_at_ms=now_ms,
                        source_timestamp_ms=now_ms,
                        staleness_ms=0,
                        fetch_latency_ms=0.0,
                        is_valid=True,
                    )

                    async with self._lock:
                        self.latest_samples[symbol] = sample
                        self.fallback_state = FallbackState.ACTIVE

                    return sample

            except asyncio.TimeoutError:
                _logger.warning("ONE_INCH_TIMEOUT: from_token=%s, to_token=%s", from_token, to_token)
                self.fallback_state = FallbackState.DEGRADED
                return None
            except Exception as e:
                _logger.warning("ONE_INCH_FETCH_ERROR: %s", str(e))
                self.fallback_state = FallbackState.DEGRADED
                return None

    async def estimate_slippage(
        self, symbol: str, borrow_amount_usdc: Decimal
    ) -> Optional[SlippageEstimate]:
        """
        Estimate price impact and slippage for a given borrow amount.
        
        Makes two quote calls (full size and 1% baseline) to compute price impact.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            borrow_amount_usdc: Size of the borrow in USDC
            
        Returns:
            SlippageEstimate with impact and recommended tolerance, or None on error
        """
        try:
            # Example: for BTC borrow, swap USDC for BTC
            from_token = "0x0000000000000000000000000000000000000000"  # USDC (update with real address)
            to_token = "0x0000000000000000000000000000000000000000"  # BTC (update with real address)

            # Baseline quote: 1% of size
            baseline_amount = borrow_amount_usdc * Decimal("0.01")
            baseline_quote = await self.fetch_swap_quote(from_token, to_token, baseline_amount)

            if not baseline_quote:
                return None

            # Full size quote
            full_quote = await self.fetch_swap_quote(from_token, to_token, borrow_amount_usdc)

            if not full_quote:
                return None

            # Compute price impact
            baseline_price = baseline_quote.mid_price
            full_price = full_quote.mid_price

            if baseline_price > 0:
                price_impact_pct = abs(full_price - baseline_price) / baseline_price * 100
            else:
                price_impact_pct = 0.0

            # Recommended slippage tolerance is impact + 0.5% buffer
            recommended_tolerance = price_impact_pct + 0.5

            # Liquidity score: inverse of impact (higher is better)
            liquidity_score = max(0.0, 100.0 - price_impact_pct)

            return SlippageEstimate(
                price_impact_pct=price_impact_pct,
                recommended_slippage_tolerance_pct=recommended_tolerance,
                liquidity_score=liquidity_score,
            )

        except Exception as e:
            _logger.warning("ONE_INCH_SLIPPAGE_ESTIMATE_ERROR: symbol=%s, error=%s", symbol, str(e))
            return None

    def get_fallback_state(self) -> FallbackState:
        """Return current health state of 1inch oracle."""
        return self.fallback_state


__all__ = ["OneInchClient"]
