"""Market stress calculator for structured risk assessment."""

from __future__ import annotations

import hashlib
import math
import os
import random
import statistics
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Tuple


@dataclass
class MarketConditions:
    symbol: str
    gas_price_gwei: float
    gas_spike_detected: bool
    funding_rate_a: float
    funding_rate_b: float
    orderbook_depth_ratio: float
    volatility_24h: float
    vix_equivalent_score: float
    funding_rate_volatility: str
    execution_risk: str
    liquidity_risk: str
    gas_spike_risk: str
    overall_risk: str
    recent_trade_summary: str = ""
    price_volatility_score: float = 0.0
    funding_divergence_score: float = 0.0
    orderbook_imbalance_score: float = 0.0
    gas_stress_score: float = 0.0


class MarketStressCalculator:
    """Derive a VIX-equivalent stress score from market inputs."""

    def __init__(self) -> None:
        self.eth_price_usdc = float(os.getenv("ETH_PRICE_USDC", "600"))
        self._historical_funding_divergence = float(os.getenv("HISTORICAL_FUNDING_DIVERGENCE", "0.001"))
        self._historical_vol_baseline = float(os.getenv("HISTORICAL_VOLATILITY_BASELINE", "0.0015"))
        self._hold_hours = float(os.getenv("ESTIMATED_HOLD_HOURS", "10"))

    def calculate_vix_equivalent(self, symbol: str) -> float:
        return round(self._cached_vix_equivalent(symbol, int(time.time() // 30)), 2)

    @lru_cache(maxsize=256)
    def _cached_vix_equivalent(self, symbol: str, cache_bucket: int) -> float:
        vol_score, funding_score, ob_score, gas_score, _, _, _ = self._score_components(symbol)
        vix_equivalent = 0.35 * vol_score + 0.25 * funding_score + 0.25 * ob_score + 0.15 * gas_score
        return max(0.0, min(100.0, vix_equivalent))

    def build_market_conditions(self, symbol: str, recent_trade_summary: str = "") -> MarketConditions:
        vol_score, funding_score, ob_score, gas_score, gas_price, gas_spike, _ = self._score_components(symbol)
        funding_rate_a, funding_rate_b = self._fetch_funding_rates(symbol)
        bid_ask = self._fetch_orderbook_depths(symbol)
        volatility_24h = self._estimate_24h_volatility(symbol)
        vix_equivalent = self.calculate_vix_equivalent(symbol)
        funding_label = self._risk_label(vix_equivalent)
        execution_label = self._risk_label(vix_equivalent)
        liquidity_label = self._liquidity_label(ob_score)
        gas_label = self._risk_label(gas_score)
        overall_label = self._overall_label(vix_equivalent, gas_spike, ob_score)
        orderbook_depth_ratio = self._average_depth_ratio(bid_ask)

        return MarketConditions(
            symbol=symbol,
            gas_price_gwei=gas_price,
            gas_spike_detected=gas_spike,
            funding_rate_a=funding_rate_a,
            funding_rate_b=funding_rate_b,
            orderbook_depth_ratio=orderbook_depth_ratio,
            volatility_24h=volatility_24h,
            vix_equivalent_score=vix_equivalent,
            funding_rate_volatility=funding_label,
            execution_risk=execution_label,
            liquidity_risk=liquidity_label,
            gas_spike_risk=gas_label,
            overall_risk=overall_label,
            recent_trade_summary=recent_trade_summary,
            price_volatility_score=vol_score,
            funding_divergence_score=funding_score,
            orderbook_imbalance_score=ob_score,
            gas_stress_score=gas_score,
        )

    def _score_components(self, symbol: str) -> Tuple[float, float, float, float, float, bool, List[float]]:
        candles = self._fetch_recent_candles(symbol)
        returns = []
        for previous, current in zip(candles, candles[1:]):
            if previous > 0 and current > 0:
                returns.append(math.log(current / previous))
        current_vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        historical_baseline = max(self._historical_vol_baseline, current_vol / 3 if current_vol else self._historical_vol_baseline)
        vol_score = min(100.0, max(0.0, (current_vol / historical_baseline) / 3.0 * 100.0)) if historical_baseline else 0.0

        funding_a, funding_b = self._fetch_funding_rates(symbol)
        funding_divergence = abs(funding_a - funding_b)
        funding_score = min(100.0, (funding_divergence / max(self._historical_funding_divergence, 1e-6)) * 100.0)

        orderbook_depths = self._fetch_orderbook_depths(symbol)
        ob_scores = []
        for bid_depth, ask_depth in orderbook_depths:
            total_depth = max(bid_depth + ask_depth, 1e-6)
            imbalance = abs(bid_depth - ask_depth) / total_depth * 100.0
            ob_scores.append(min(100.0, max(0.0, imbalance)))
        ob_score = sum(ob_scores) / len(ob_scores) if ob_scores else 0.0

        gas_price, avg_gas_7d, std_gas_7d = self._fetch_gas_context(symbol)
        gas_spike = gas_price > avg_gas_7d * 1.3
        gas_score = (gas_price - avg_gas_7d) / max(std_gas_7d, 1e-6) * 25.0
        gas_score = min(100.0, max(0.0, gas_score))

        return vol_score, funding_score, ob_score, gas_score, gas_price, gas_spike, returns

    def _fetch_recent_candles(self, symbol: str) -> List[float]:
        base_prices = {
            "BTC": 43000.0,
            "ETH": 2300.0,
            "USDC": 1.0,
        }
        base = base_prices.get(symbol.upper(), 1000.0)
        seed_source = f"{symbol}:{int(time.time() // 30)}".encode("utf-8")
        seed = int(hashlib.sha256(seed_source).hexdigest()[:16], 16)
        rng = random.Random(seed)
        candles = []
        for index in range(100):
            drift = math.sin(index / 9.0) * 0.0015
            noise = rng.uniform(-0.004, 0.004)
            base *= max(0.98, 1.0 + drift + noise)
            candles.append(max(0.01, base))
        return candles

    def _fetch_funding_rates(self, symbol: str) -> Tuple[float, float]:
        seed_source = f"funding:{symbol}:{int(time.time() // 30)}".encode("utf-8")
        seed = int(hashlib.sha256(seed_source).hexdigest()[:16], 16)
        rng = random.Random(seed)
        center = rng.uniform(-0.0005, 0.0015)
        spread = rng.uniform(0.0001, 0.0008)
        return center + spread, center - spread

    def _fetch_orderbook_depths(self, symbol: str) -> List[Tuple[float, float]]:
        seed_source = f"depth:{symbol}:{int(time.time() // 30)}".encode("utf-8")
        seed = int(hashlib.sha256(seed_source).hexdigest()[:16], 16)
        rng = random.Random(seed)
        return [
            (rng.uniform(100000.0, 1200000.0), rng.uniform(100000.0, 1200000.0)),
            (rng.uniform(100000.0, 1200000.0), rng.uniform(100000.0, 1200000.0)),
        ]

    def _fetch_gas_context(self, symbol: str) -> Tuple[float, float, float]:
        seed_source = f"gas:{symbol}:{int(time.time() // 30)}".encode("utf-8")
        seed = int(hashlib.sha256(seed_source).hexdigest()[:16], 16)
        rng = random.Random(seed)
        avg_gas = rng.uniform(20.0, 45.0)
        std_gas = rng.uniform(2.0, 8.0)
        current_gas = max(1.0, avg_gas + rng.uniform(-1.5, 3.0) * std_gas)
        return current_gas, avg_gas, std_gas

    def _estimate_24h_volatility(self, symbol: str) -> float:
        candles = self._fetch_recent_candles(symbol)
        returns = []
        for previous, current in zip(candles, candles[1:]):
            if previous > 0 and current > 0:
                returns.append(math.log(current / previous))
        vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        return round(vol * 100.0, 4)

    def _average_depth_ratio(self, depths: List[Tuple[float, float]]) -> float:
        if not depths:
            return 0.0
        ratios = []
        for bid_depth, ask_depth in depths:
            total_depth = max(bid_depth + ask_depth, 1e-6)
            ratios.append(abs(bid_depth - ask_depth) / total_depth)
        return round(sum(ratios) / len(ratios), 4)

    def _risk_label(self, score: float) -> str:
        if score <= 33:
            return "LOW"
        if score <= 66:
            return "MODERATE"
        return "HIGH"

    def _liquidity_label(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 60:
            return "MEDIUM"
        return "HIGH"

    def _overall_label(self, vix_score: float, gas_spike: bool, ob_score: float) -> str:
        if gas_spike or ob_score > 70 or vix_score > 66:
            return "HIGH"
        if vix_score > 33 or ob_score > 35:
            return "MODERATE"
        return "LOW"
