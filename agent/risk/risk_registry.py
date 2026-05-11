"""Thread-safe circuit breaker registry."""

from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agent.risk_manager import (
    BORROW_RATE_JUMP_THRESHOLD_PCT,
    BreakerType,
    CircuitBreakerEvent,
    CircuitBreakerState,
    DAILY_LOSS_CAP_USDC,
    GAS_SPIKE_THRESHOLD_PCT,
    HUMAN_OVERRIDE_WINDOW_SECONDS,
    LARGE_TRADE_THRESHOLD_USDC,
    MAX_COLLATERAL_RATIO,
    MAX_CONCURRENT_POSITIONS,
    MAX_SLIPPAGE_PCT,
    POSITION_TIMEOUT_SECONDS,
    RiskLevel,
    RiskSnapshot,
)

_logger = logging.getLogger(__name__)


def _threshold_for_breaker(breaker_type: BreakerType) -> float:
    mapping = {
        BreakerType.GAS_SPIKE: GAS_SPIKE_THRESHOLD_PCT,
        BreakerType.SLIPPAGE_EXCEEDED: MAX_SLIPPAGE_PCT,
        BreakerType.BORROW_RATE_JUMP: BORROW_RATE_JUMP_THRESHOLD_PCT,
        BreakerType.MAX_CONCURRENT_POSITIONS: float(MAX_CONCURRENT_POSITIONS),
        BreakerType.DAILY_LOSS_CAP: float(DAILY_LOSS_CAP_USDC),
        BreakerType.MAX_COLLATERAL_RATIO: MAX_COLLATERAL_RATIO,
        BreakerType.POSITION_TIMEOUT: float(POSITION_TIMEOUT_SECONDS),
        BreakerType.INSUFFICIENT_BALANCE: 0.0,
        BreakerType.HUMAN_OVERRIDE: float(LARGE_TRADE_THRESHOLD_USDC),
    }
    return float(mapping[breaker_type])


def _risk_level(open_breakers: List[BreakerType], concurrent_positions: int, daily_pnl: Decimal) -> RiskLevel:
    if BreakerType.HUMAN_OVERRIDE in open_breakers or BreakerType.DAILY_LOSS_CAP in open_breakers or BreakerType.POSITION_TIMEOUT in open_breakers:
        return RiskLevel.BLACK
    if open_breakers:
        return RiskLevel.RED
    if concurrent_positions >= MAX_CONCURRENT_POSITIONS - 1 or daily_pnl <= DAILY_LOSS_CAP_USDC * Decimal("0.5"):
        return RiskLevel.YELLOW
    return RiskLevel.GREEN


class RiskRegistry:
    def __init__(self, data_dir: str = "data", audit_logger: Any = None):
        self.lock = threading.RLock()
        self.breaker_states: Dict[BreakerType, CircuitBreakerState] = {breaker: CircuitBreakerState.CLOSED for breaker in BreakerType}
        self.reset_schedule: Dict[BreakerType, int] = {}
        self.breaker_events: List[CircuitBreakerEvent] = []
        self.daily_pnl: Decimal = Decimal("0")
        self.concurrent_positions: int = 0
        self.current_collateral_ratio: float = 0.0
        self.gas_price_gwei: float = 0.0
        self.current_borrow_rate: float = 0.0
        self.audit_logger = audit_logger
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def update_market_state(self, gas_price_gwei: Optional[float] = None, current_borrow_rate: Optional[float] = None, current_collateral_ratio: Optional[float] = None) -> None:
        with self.lock:
            if gas_price_gwei is not None:
                self.gas_price_gwei = gas_price_gwei
            if current_borrow_rate is not None:
                self.current_borrow_rate = current_borrow_rate
            if current_collateral_ratio is not None:
                self.current_collateral_ratio = current_collateral_ratio

    def is_trading_allowed(self) -> tuple[bool, List[BreakerType]]:
        now = int(time.time())
        blocked: List[BreakerType] = []
        with self.lock:
            for breaker_type, state in self.breaker_states.items():
                if state == CircuitBreakerState.OPEN:
                    reset_at = self.reset_schedule.get(breaker_type)
                    if reset_at is not None and now >= reset_at:
                        self.breaker_states[breaker_type] = CircuitBreakerState.HALF_OPEN
                        continue
                    blocked.append(breaker_type)
            return (len(blocked) == 0, blocked)

    def open_breaker(self, breaker_type: BreakerType, trigger_value: float, opportunity_id: Optional[str], auto_reset_seconds: Optional[int], notes: str) -> CircuitBreakerEvent:
        with self.lock:
            now = int(time.time())
            threshold_value = _threshold_for_breaker(breaker_type)
            event = CircuitBreakerEvent(
                event_id=str(uuid4()),
                breaker_type=breaker_type,
                state_before=self.breaker_states.get(breaker_type, CircuitBreakerState.CLOSED),
                state_after=CircuitBreakerState.OPEN,
                trigger_value=trigger_value,
                threshold_value=threshold_value,
                opportunity_id=opportunity_id,
                triggered_at=now,
                auto_reset_at=now + auto_reset_seconds if auto_reset_seconds is not None else None,
                resolved_at=None,
                resolution_method=None,
                notes=notes,
            )
            self.breaker_states[breaker_type] = CircuitBreakerState.OPEN
            if auto_reset_seconds is not None:
                self.reset_schedule[breaker_type] = now + auto_reset_seconds
            else:
                self.reset_schedule.pop(breaker_type, None)
            self.breaker_events.append(event)
            _logger.critical(
                "CIRCUIT_BREAKER_OPENED: type=%s, trigger=%s, threshold=%s",
                breaker_type.value,
                trigger_value,
                threshold_value,
            )
            if self.audit_logger is not None:
                self.audit_logger.record_event(event)
        return event

    def close_breaker(self, breaker_type: BreakerType, resolution_method: str) -> CircuitBreakerEvent:
        with self.lock:
            now = int(time.time())
            threshold_value = _threshold_for_breaker(breaker_type)
            event = CircuitBreakerEvent(
                event_id=str(uuid4()),
                breaker_type=breaker_type,
                state_before=self.breaker_states.get(breaker_type, CircuitBreakerState.CLOSED),
                state_after=CircuitBreakerState.CLOSED,
                trigger_value=0.0,
                threshold_value=threshold_value,
                opportunity_id=None,
                triggered_at=now,
                auto_reset_at=None,
                resolved_at=now,
                resolution_method=resolution_method,
                notes=f"Breaker {breaker_type.value} closed via {resolution_method}",
            )
            self.breaker_states[breaker_type] = CircuitBreakerState.CLOSED
            self.reset_schedule.pop(breaker_type, None)
            self.breaker_events.append(event)
            _logger.info("CIRCUIT_BREAKER_CLOSED: type=%s, method=%s", breaker_type.value, resolution_method)
            if self.audit_logger is not None:
                self.audit_logger.record_event(event)
        return event

    def get_snapshot(self) -> RiskSnapshot:
        with self.lock:
            allowed, _ = self.is_trading_allowed()
            open_breakers = [breaker for breaker, state in self.breaker_states.items() if state == CircuitBreakerState.OPEN]
            risk_level = _risk_level(open_breakers, self.concurrent_positions, self.daily_pnl)
            portfolio_heat = min(
                1.0,
                (
                    min(self.concurrent_positions / max(1, MAX_CONCURRENT_POSITIONS), 1.0) * 0.35
                    + min(max(float(-self.daily_pnl / Decimal("50")), 0.0), 1.0) * 0.25
                    + min(max(self.gas_price_gwei / 100.0, 0.0), 1.0) * 0.2
                    + min(max(self.current_borrow_rate / 5.0, 0.0), 1.0) * 0.2
                ),
            )
            return RiskSnapshot(
                snapshot_id=str(uuid4()),
                risk_level=risk_level,
                open_breakers=open_breakers,
                concurrent_positions=self.concurrent_positions,
                daily_pnl_usdc=self.daily_pnl,
                current_collateral_ratio=self.current_collateral_ratio,
                gas_price_gwei=self.gas_price_gwei,
                current_borrow_rate=self.current_borrow_rate,
                portfolio_heat=portfolio_heat,
                trading_allowed=allowed,
                captured_at=int(time.time()),
            )
