"""Estimate gas before building a transaction so unprofitable trades can be dropped early."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Deque, Optional

from agent.execution.gas_monitor import GasMonitor, DEFAULT_ETH_PRICE_USDC

from .constants import (
    DEFAULT_ETH_PRICE_USDC as DEFAULT_OPTIMIZER_ETH_PRICE_USDC,
    DEX_ROUTING_GAS_PER_LEG,
    FLASHLOAN_OVERHEAD_GAS,
    MEV_BURN_BASE_GAS,
    MEV_BURN_PCT,
    MEV_BURN_THRESHOLD_USDC,
    PROFIT_SETTLEMENT_GAS,
    SIGNAL_VALIDATION_GAS_BUDGET,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfitabilityCheck:
    profitable: bool
    expected_profit: Decimal
    estimated_gas_cost: Decimal
    estimated_mev_burn: Decimal
    net_profit: Decimal
    margin_pct: float


@dataclass(frozen=True)
class GasEstimateObservation:
    estimated_gas_units: int
    actual_gas_used: int
    error_pct: float


class GasEstimator:
    def __init__(self, gas_monitor: Optional[GasMonitor] = None, eth_price_usdc: Optional[Decimal] = None) -> None:
        self.gas_monitor = gas_monitor or GasMonitor(web3=None, poll_interval_seconds=30)
        self.eth_price_usdc = eth_price_usdc or DEFAULT_OPTIMIZER_ETH_PRICE_USDC or DEFAULT_ETH_PRICE_USDC
        self._recent_observations: Deque[GasEstimateObservation] = deque(maxlen=50)
        self._last_expected_profit_usdc = Decimal("0")
        self._last_mev_burn_amount_usdc = Decimal("0")

    def estimate_gas_units(self, batch_size: int, mev_burn_active: bool) -> int:
        gas_units = FLASHLOAN_OVERHEAD_GAS + batch_size * (
            SIGNAL_VALIDATION_GAS_BUDGET + 2 * DEX_ROUTING_GAS_PER_LEG + PROFIT_SETTLEMENT_GAS
        )
        if mev_burn_active:
            gas_units += MEV_BURN_BASE_GAS
        return gas_units

    def estimate_mev_burn_amount_usdc(self, expected_profit_usdc: Decimal) -> Decimal:
        if expected_profit_usdc <= MEV_BURN_THRESHOLD_USDC:
            return Decimal("0")
        return expected_profit_usdc * MEV_BURN_PCT / Decimal("100")

    def estimate_gas_cost_usdc(self, batch_size: int, mev_burn_active: bool) -> Decimal:
        fees = self.gas_monitor.get_current_fees()
        gas_units = Decimal(self.estimate_gas_units(batch_size, mev_burn_active))
        gas_cost = gas_units * Decimal(str(fees.max_fee_gwei)) * Decimal("1e-9") * self.eth_price_usdc
        if mev_burn_active:
            gas_cost += self._last_mev_burn_amount_usdc
        return gas_cost

    def is_profitable_after_gas(
        self,
        expected_profit_usdc: Decimal,
        batch_size: int,
        mev_burn_active: bool,
    ) -> ProfitabilityCheck:
        self._last_expected_profit_usdc = expected_profit_usdc
        self._last_mev_burn_amount_usdc = (
            self.estimate_mev_burn_amount_usdc(expected_profit_usdc) if mev_burn_active else Decimal("0")
        )

        estimated_gas_cost = self.estimate_gas_cost_usdc(batch_size, mev_burn_active)
        net_profit = expected_profit_usdc - estimated_gas_cost - self._last_mev_burn_amount_usdc
        margin_pct = float((net_profit / expected_profit_usdc) * Decimal("100")) if expected_profit_usdc > 0 else 0.0

        return ProfitabilityCheck(
            profitable=net_profit > 0,
            expected_profit=expected_profit_usdc,
            estimated_gas_cost=estimated_gas_cost,
            estimated_mev_burn=self._last_mev_burn_amount_usdc,
            net_profit=net_profit,
            margin_pct=margin_pct,
        )

    def record_gas_estimate(self, estimated_gas_units: int, actual_gas_used: int) -> GasEstimateObservation:
        error_pct = abs(actual_gas_used - estimated_gas_units) / actual_gas_used * 100 if actual_gas_used else 0.0
        observation = GasEstimateObservation(
            estimated_gas_units=estimated_gas_units,
            actual_gas_used=actual_gas_used,
            error_pct=error_pct,
        )
        self._recent_observations.append(observation)
        _logger.info(
            "GAS_ESTIMATE_ACCURACY: estimated=%s, actual=%s, error_pct=%.1f%%",
            estimated_gas_units,
            actual_gas_used,
            error_pct,
        )
        return observation

    def recent_observations(self) -> list[GasEstimateObservation]:
        return list(self._recent_observations)
