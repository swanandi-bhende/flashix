from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DexFill:
    filled_amount: float
    avg_price: float


class MockDEXRouter:
    def __init__(self, base_price: float = 100.0, slippage_mean: float = 0.01, slippage_std: float = 0.005) -> None:
        self.base_price = base_price
        self.slippage_mean = slippage_mean
        self.slippage_std = slippage_std
        self.scenario_overrides: dict[str, tuple[float, float]] = {
            "ZERO_LIQUIDITY": (0.12, 0.15),
            "FLASH_CRASH": (0.05, 0.08),
            "NETWORK_CONGESTION": (0.02, 0.01),
        }
        self.active_scenario = "NORMAL"

    def set_scenario(self, scenario_type: str) -> None:
        self.active_scenario = scenario_type

    def execute_long(self, amount: float, price: float | None = None) -> tuple[float, float]:
        scenario_mean, scenario_std = self.scenario_overrides.get(self.active_scenario, (self.slippage_mean, self.slippage_std))
        slippage = max(0.0, random.gauss(scenario_mean, scenario_std))
        trade_price = price if price is not None else self.base_price
        filled_amount = amount * (1.0 - slippage)
        avg_price = trade_price * (1.0 + slippage / 2.0)
        return filled_amount, avg_price

    def execute_short(self, amount: float, price: float | None = None) -> tuple[float, float]:
        scenario_mean, scenario_std = self.scenario_overrides.get(self.active_scenario, (self.slippage_mean, self.slippage_std))
        slippage = max(0.0, random.gauss(scenario_mean, scenario_std))
        trade_price = price if price is not None else self.base_price
        filled_amount = amount * (1.0 - slippage)
        avg_price = trade_price * (1.0 - slippage / 2.0)
        return filled_amount, avg_price
