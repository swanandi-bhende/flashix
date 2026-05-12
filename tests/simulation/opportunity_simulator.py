from __future__ import annotations

import itertools
import logging
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from statistics import median
from uuid import uuid4

from compute.arbitrage_analyzer import analyze
from tests.integration_test import HistoricalDataset, SimulatedOpportunity, now_ms
from tests.replay.test_case_generator import TestCaseGenerator

logger = logging.getLogger(__name__)


class OpportunitySimulator:
    def __init__(self, fixture_path: str = "tests/fixtures/test_cases.json") -> None:
        self.test_case_generator = TestCaseGenerator(fixture_path)

    def _symbol_price_map(self, dataset: HistoricalDataset) -> dict[str, dict[int, dict[str, float]]]:
        mapped: dict[str, dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
        for symbol, series in dataset.price_series.items():
            for point in series:
                mapped[symbol][point.timestamp][point.exchange] = point.price
        return mapped

    def _funding_lookup(self, dataset: HistoricalDataset, symbol: str, exchange: str) -> float:
        points = dataset.funding_rate_series.get(symbol, [])
        exchange_points = [point.funding_rate for point in points if point.exchange == exchange]
        if not exchange_points:
            return 0.0001
        return float(exchange_points[-1])

    def _gas_lookup(self, dataset: HistoricalDataset, timestamp: int) -> float:
        if not dataset.gas_price_series:
            return 30.0
        nearest = min(dataset.gas_price_series, key=lambda point: abs(point.timestamp - timestamp))
        return float(nearest.gas_price_gwei)

    def _build_opportunity(self, symbol: str, timestamp: int, price_hl: float, price_dydx: float, dataset: HistoricalDataset, spread_pct: float, historical_outcome: str, duration_minutes: int) -> SimulatedOpportunity:
        borrow_amount = 10_000.0
        gross_spread = abs(price_hl - price_dydx) / min(price_hl, price_dydx) * 100.0
        funding_rate_a = self._funding_lookup(dataset, symbol, "dydx")
        funding_rate_b = self._funding_lookup(dataset, symbol, "hyperliquid")
        gas_price = self._gas_lookup(dataset, timestamp)

        payload = {
            "opportunity_id": f"{symbol}-{timestamp}",
            "symbol": symbol,
            "dex_a": "hyperliquid",
            "dex_b": "dydx",
            "price_a": Decimal(str(price_hl)),
            "price_b": Decimal(str(price_dydx)),
            "borrow_amount_usdc": Decimal(str(borrow_amount)),
            "funding_rate_a": Decimal(str(funding_rate_a)),
            "funding_rate_b": Decimal(str(funding_rate_b)),
            "orderbook_depth_a": 50_000.0,
            "orderbook_depth_b": 50_000.0,
            "trade_flow_imbalance_a": 0.03,
            "trade_flow_imbalance_b": -0.02,
            "volatility_24h": 0.8,
            "correlation_btc": 0.25,
            "timestamp": timestamp // 1000,
            "chain_id": 16600,
            "gas_price_gwei": gas_price,
            "spread_momentum_5s": 0.01,
        }
        analysis = analyze(payload)
        result = analysis.get("result", {})
        expected_profit = float(Decimal(str(result.get("expected_profit_usdc", "0"))))
        if historical_outcome == "REVERTED":
            expected_profit = max(0.0, expected_profit * 0.35)
        return SimulatedOpportunity(
            id=str(uuid4()),
            symbol=symbol,
            dex_a="hyperliquid",
            dex_b="dydx",
            price_a=float(price_hl),
            price_b=float(price_dydx),
            gross_spread_pct=gross_spread,
            funding_rate_a=float(funding_rate_a),
            funding_rate_b=float(funding_rate_b),
            gas_price_gwei=float(gas_price),
            timestamp=timestamp,
            expected_duration_minutes=duration_minutes,
            historical_outcome=historical_outcome,  # type: ignore[arg-type]
            expected_profit_usdc=expected_profit,
            gap_ms=60_000,
            scenario_type="HISTORICAL_REPLAY",
            edge_case_type="",
            collateral_ratio=1.6,
            market_state={"spread_pct": spread_pct, "price_hyperliquid": price_hl, "price_dydx": price_dydx},
        )

    def generate_opportunities(self, dataset: HistoricalDataset, n_target: int = 120) -> list[SimulatedOpportunity]:
        opportunities: list[SimulatedOpportunity] = []
        price_map = self._symbol_price_map(dataset)

        for symbol, minute_map in price_map.items():
            ordered_timestamps = sorted(minute_map)
            spread_windows: list[tuple[int, int]] = []
            current_start: int | None = None
            streak = 0
            for timestamp in ordered_timestamps:
                prices = minute_map[timestamp]
                if "hyperliquid" not in prices or "dydx" not in prices:
                    current_start = None
                    streak = 0
                    continue
                price_hl = prices["hyperliquid"]
                price_dydx = prices["dydx"]
                spread_pct = abs(price_hl - price_dydx) / min(price_hl, price_dydx) * 100.0
                if spread_pct > 0.5:
                    streak += 1
                    current_start = current_start or timestamp
                else:
                    if current_start is not None and streak >= 2:
                        spread_windows.append((current_start, timestamp))
                    current_start = None
                    streak = 0
            if current_start is not None and streak >= 2:
                spread_windows.append((current_start, ordered_timestamps[-1]))

            for start_ts, end_ts in spread_windows:
                timestamps = [ts for ts in ordered_timestamps if start_ts <= ts <= end_ts]
                if not timestamps:
                    continue
                for timestamp in timestamps:
                    prices = minute_map[timestamp]
                    price_hl = prices["hyperliquid"]
                    price_dydx = prices["dydx"]
                    spread_pct = abs(price_hl - price_dydx) / min(price_hl, price_dydx) * 100.0
                    future_window = [minute_map.get(ts, {}) for ts in ordered_timestamps if ts >= timestamp][:4]
                    future_spreads = [
                        abs(item.get("hyperliquid", price_hl) - item.get("dydx", price_dydx)) / min(item.get("hyperliquid", price_hl), item.get("dydx", price_dydx)) * 100.0
                        for item in future_window
                        if item.get("hyperliquid") and item.get("dydx")
                    ]
                    historical_outcome = "PROFITABLE" if len([value for value in future_spreads if value > 0.5]) >= 3 else "REVERTED"
                    opportunities.append(
                        self._build_opportunity(
                            symbol=symbol,
                            timestamp=timestamp,
                            price_hl=price_hl,
                            price_dydx=price_dydx,
                            dataset=dataset,
                            spread_pct=spread_pct,
                            historical_outcome=historical_outcome,
                            duration_minutes=max(3, len(future_spreads)),
                        )
                    )
                    if len(opportunities) >= n_target:
                        return opportunities[:n_target]

        synthetic_opportunities: list[SimulatedOpportunity] = []
        for test_case in self.test_case_generator.generate_all():
            synthetic_opportunities.append(
                SimulatedOpportunity(
                    id=test_case.test_id,
                    symbol=test_case.input.symbol,
                    dex_a=test_case.input.dex_a,
                    dex_b=test_case.input.dex_b,
                    price_a=float(test_case.input.price_a),
                    price_b=float(test_case.input.price_b),
                    gross_spread_pct=abs(float(test_case.input.price_a) - float(test_case.input.price_b)) / min(float(test_case.input.price_a), float(test_case.input.price_b)) * 100.0,
                    funding_rate_a=float(test_case.input.funding_rate_a),
                    funding_rate_b=float(test_case.input.funding_rate_b),
                    gas_price_gwei=float(test_case.input.gas_price_gwei),
                    timestamp=int(test_case.input.timestamp) * 1000,
                    expected_duration_minutes=3,
                    historical_outcome="PROFITABLE" if test_case.expected_decision == "EXECUTE" else "REVERTED",
                    expected_profit_usdc=float((test_case.expected_profit_range[0] + test_case.expected_profit_range[1]) / Decimal("2")) if test_case.expected_profit_range else 0.0,
                    gap_ms=60_000,
                    scenario_type=str(test_case.scenario_type),
                    edge_case_type=str(test_case.scenario_type),
                    collateral_ratio=1.6,
                    market_state={"replay_case": test_case.test_name},
                )
            )
            if len(synthetic_opportunities) >= 25:
                break

        historical_keep = max(0, n_target - len(synthetic_opportunities))
        selected = opportunities[:historical_keep] + synthetic_opportunities[: max(0, n_target - historical_keep)]
        if len(selected) < n_target and len(opportunities) > historical_keep:
            selected.extend(opportunities[historical_keep:n_target])
        return selected[:n_target]

    def inject_edge_cases(self, opportunities: list[SimulatedOpportunity]) -> list[SimulatedOpportunity]:
        edge_cases = [
            (5, "LIQUIDATION_SCENARIO"),
            (10, "FUNDING_RATE_SPIKE"),
            (15, "NETWORK_DELAY_MILD"),
            (20, "NETWORK_DELAY_SEVERE"),
            (25, "GAS_SPIKE"),
            (30, "MODEL_DRIFT_EARLY"),
            (35, "ZERO_LIQUIDITY"),
            (40, "FLASH_CRASH"),
            (45, "COLLATERAL_DROP_10PCT"),
            (50, "MODEL_DRIFT_LATE"),
            (55, "LIQUIDATION_SCENARIO_REPEAT"),
            (60, "FUNDING_RATE_SPIKE_REPEAT"),
            (65, "NETWORK_DELAY_MILD_REPEAT"),
            (70, "NETWORK_DELAY_SEVERE_REPEAT"),
            (75, "GAS_SPIKE_REPEAT"),
            (80, "MODEL_DRIFT_EARLY_REPEAT"),
            (85, "ZERO_LIQUIDITY_REPEAT"),
            (90, "FLASH_CRASH_REPEAT"),
            (95, "COLLATERAL_DROP_10PCT_REPEAT"),
            (100, "MODEL_DRIFT_LATE_REPEAT"),
        ]
        logger.info("EDGE_CASE_INJECTION_POSITIONS: %s", ", ".join(f"{pos}:{kind}" for pos, kind in edge_cases))

        result = list(opportunities)
        for position, edge_case_type in edge_cases:
            if not result:
                break
            insert_at = min(max(position - 1, 0), len(result))
            base = result[insert_at - 1 if insert_at > 0 else 0]
            result.insert(
                insert_at,
                SimulatedOpportunity(
                    id=f"edge-{edge_case_type.lower()}-{position}",
                    symbol=base.symbol,
                    dex_a=base.dex_a,
                    dex_b=base.dex_b,
                    price_a=base.price_a * (0.8 if "FLASH_CRASH" in edge_case_type else 1.0),
                    price_b=base.price_b,
                    gross_spread_pct=base.gross_spread_pct,
                    funding_rate_a=0.009 if "FUNDING_RATE_SPIKE" in edge_case_type else base.funding_rate_a,
                    funding_rate_b=base.funding_rate_b,
                    gas_price_gwei=base.gas_price_gwei * (1.4 if "GAS_SPIKE" in edge_case_type else 1.0),
                    timestamp=base.timestamp,
                    expected_duration_minutes=base.expected_duration_minutes,
                    historical_outcome="REVERTED" if "REVERT" not in edge_case_type else "REVERTED",
                    expected_profit_usdc=base.expected_profit_usdc,
                    gap_ms=base.gap_ms,
                    scenario_type=edge_case_type,
                    edge_case_type=edge_case_type,
                    collateral_ratio=0.9 if "LIQUIDATION" in edge_case_type else (1.44 if "COLLATERAL_DROP_10PCT" in edge_case_type else base.collateral_ratio),
                    market_state={"edge_case": edge_case_type},
                ),
            )
        return result
