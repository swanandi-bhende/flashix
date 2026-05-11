"""Central risk vocabulary and RiskManager façade."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agent.execution_engine import ExecutionRequest, ExecutionResult


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class RiskLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    BLACK = "BLACK"


class BreakerType(str, Enum):
    GAS_SPIKE = "GAS_SPIKE"
    SLIPPAGE_EXCEEDED = "SLIPPAGE_EXCEEDED"
    BORROW_RATE_JUMP = "BORROW_RATE_JUMP"
    MAX_CONCURRENT_POSITIONS = "MAX_CONCURRENT_POSITIONS"
    DAILY_LOSS_CAP = "DAILY_LOSS_CAP"
    MAX_COLLATERAL_RATIO = "MAX_COLLATERAL_RATIO"
    POSITION_TIMEOUT = "POSITION_TIMEOUT"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"


GAS_SPIKE_THRESHOLD_PCT = 30.0
GAS_SPIKE_WINDOW_SECONDS = 30
MAX_SLIPPAGE_PCT = 2.0
BORROW_RATE_JUMP_THRESHOLD_PCT = 0.5
MAX_CONCURRENT_POSITIONS = 3
DAILY_LOSS_CAP_USDC = Decimal("-50.0")
MAX_COLLATERAL_RATIO = 2.0
MIN_COLLATERAL_RATIO = 1.5
POSITION_TIMEOUT_SECONDS = 30
HUMAN_OVERRIDE_WINDOW_SECONDS = 5
LARGE_TRADE_THRESHOLD_USDC = Decimal("10.0")


ResolutionMethod = Literal["AUTO_RESET", "MANUAL_RESET", "CONDITION_CLEARED"]


@dataclass(frozen=True)
class CircuitBreakerEvent:
    event_id: str
    breaker_type: BreakerType
    state_before: CircuitBreakerState
    state_after: CircuitBreakerState
    trigger_value: float
    threshold_value: float
    opportunity_id: Optional[str]
    triggered_at: int
    auto_reset_at: Optional[int]
    resolved_at: Optional[int]
    resolution_method: Optional[ResolutionMethod]
    notes: str


@dataclass(frozen=True)
class RiskSnapshot:
    snapshot_id: str
    risk_level: RiskLevel
    open_breakers: List[BreakerType]
    concurrent_positions: int
    daily_pnl_usdc: Decimal
    current_collateral_ratio: float
    gas_price_gwei: float
    current_borrow_rate: float
    portfolio_heat: float
    trading_allowed: bool
    captured_at: int


@dataclass(frozen=True)
class SpikeCheckResult:
    spike_detected: bool
    spike_pct: float = 0.0
    baseline_fee_gwei: float = 0.0
    current_fee_gwei: float = 0.0
    window_size: int = 0
    reason: str = ""


@dataclass(frozen=True)
class SlippageCheck:
    slippage_pct: float
    avg_slippage_5_trades: float
    avg_slippage_20_trades: float
    breaker_opened: bool
    reason: str


@dataclass(frozen=True)
class LimitCheck:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class PositionRecord:
    opportunity_id: str
    opened_at: int
    borrow_amount: Decimal
    expected_close_at: int
    tx_hash: str


@dataclass(frozen=True)
class OverrideResult:
    approved: bool
    method: str
    waited_seconds: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class RiskCheckResult:
    allowed: bool
    blocking_reason: Optional[str]
    blocking_breakers: List[BreakerType]
    human_override_result: Optional[OverrideResult]
    check_latency_ms: float


@dataclass(frozen=True)
class BreakerAnalytics:
    total_events: int
    events_by_type: Dict[BreakerType, int]
    most_frequent_breaker: Optional[BreakerType]
    avg_time_open_seconds_by_type: Dict[BreakerType, float]
    false_positive_rate_estimate: float
    trading_uptime_pct: float


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _enum_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_enum_value(item) for item in value]
    return value


def _risk_level_from_state(open_breakers: List[BreakerType], concurrent_positions: int, daily_pnl: Decimal) -> RiskLevel:
    if BreakerType.HUMAN_OVERRIDE in open_breakers or BreakerType.DAILY_LOSS_CAP in open_breakers or BreakerType.POSITION_TIMEOUT in open_breakers:
        return RiskLevel.BLACK
    if open_breakers:
        return RiskLevel.RED
    if concurrent_positions >= MAX_CONCURRENT_POSITIONS - 1 or daily_pnl <= DAILY_LOSS_CAP_USDC * Decimal("0.5"):
        return RiskLevel.YELLOW
    return RiskLevel.GREEN


class RiskManager:
    """Aggregates all risk components behind a single pre-execution gate."""

    def __init__(self, web3: Any = None, lending_pool: Any = None, data_dir: str = "data", auto_start: bool = True):
        from agent.risk.gas_circuit_breaker import GasCircuitBreaker
        from agent.risk.human_override import HumanOverrideGate
        from agent.risk.portfolio_limits import PortfolioLimitsEnforcer
        from agent.risk.position_watchdog import PositionWatchdog
        from agent.risk.risk_audit_logger import RiskAuditLogger
        from agent.risk.risk_registry import RiskRegistry
        from agent.risk.trade_circuit_breakers import BorrowRateCircuitBreaker, SlippageCircuitBreaker

        self.web3 = web3
        self.lending_pool = lending_pool
        self.registry = RiskRegistry(data_dir=data_dir)
        self.audit_logger = RiskAuditLogger(data_dir=data_dir, registry=self.registry)
        self.registry.audit_logger = self.audit_logger

        self.gas_breaker = GasCircuitBreaker(registry=self.registry, web3=web3, data_dir=data_dir)
        self.slippage_breaker = SlippageCircuitBreaker(registry=self.registry, data_dir=data_dir)
        self.borrow_rate_breaker = BorrowRateCircuitBreaker(registry=self.registry, lending_pool=lending_pool, data_dir=data_dir)
        self.portfolio_limits = PortfolioLimitsEnforcer(registry=self.registry, data_dir=data_dir)
        self.position_watchdog = PositionWatchdog(registry=self.registry, data_dir=data_dir, auto_start=auto_start)
        self.human_override_gate = HumanOverrideGate(registry=self.registry, data_dir=data_dir)

        if auto_start:
            self.gas_breaker.start_monitoring()
            self.borrow_rate_breaker.start_monitoring()
            self.portfolio_limits.reset_daily_pnl_at_midnight()

    def pre_execution_check(self, request: "ExecutionRequest") -> RiskCheckResult:
        started_at = time.perf_counter()

        allowed, blocking_breakers = self.registry.is_trading_allowed()
        if not allowed:
            return RiskCheckResult(
                allowed=False,
                blocking_reason=f"Trading blocked by {[breaker.value for breaker in blocking_breakers]}",
                blocking_breakers=blocking_breakers,
                human_override_result=None,
                check_latency_ms=(time.perf_counter() - started_at) * 1000,
            )

        concurrent_check = self.portfolio_limits.check_concurrent_positions()
        if not concurrent_check.allowed:
            return RiskCheckResult(False, concurrent_check.reason, [BreakerType.MAX_CONCURRENT_POSITIONS], None, (time.perf_counter() - started_at) * 1000)

        collateral_check = self.portfolio_limits.check_collateral_ratio(request.borrow_amount_usdc, request.collateral_amount_usdc)
        if not collateral_check.allowed:
            return RiskCheckResult(False, collateral_check.reason, [], None, (time.perf_counter() - started_at) * 1000)

        gas_check = self.gas_breaker.check_spike()
        if gas_check.spike_detected:
            return RiskCheckResult(False, f"Gas spike detected: {gas_check.spike_pct:.2f}%", [BreakerType.GAS_SPIKE], None, (time.perf_counter() - started_at) * 1000)

        borrow_check = self.borrow_rate_breaker.check_current_rate()
        if not borrow_check.allowed:
            return RiskCheckResult(False, borrow_check.reason, [BreakerType.BORROW_RATE_JUMP], None, (time.perf_counter() - started_at) * 1000)

        override_result = self.human_override_gate.request_approval(
            request.opportunity_id,
            request.signal.expected_profit_usdc,
            signal_summary=getattr(request.signal, "reasoning", ""),
        )
        if not override_result.approved:
            return RiskCheckResult(False, override_result.notes or "Operator halted execution", [BreakerType.HUMAN_OVERRIDE], override_result, (time.perf_counter() - started_at) * 1000)

        return RiskCheckResult(True, None, [], override_result, (time.perf_counter() - started_at) * 1000)

    def on_position_opened(self, opportunity_id: str, tx_hash: str, borrow_amount: Decimal) -> None:
        self.portfolio_limits.on_position_opened(opportunity_id)
        self.position_watchdog.register_position(opportunity_id, tx_hash, borrow_amount)

    def post_execution_update(self, result: "ExecutionResult", request: "ExecutionRequest") -> None:
        realized = result.realized_profit_usdc if result.realized_profit_usdc is not None else Decimal("0")
        with self.registry.lock:
            self.portfolio_limits.on_position_closed(request.opportunity_id, realized)
            self.slippage_breaker.check_post_execution_slippage(request.signal.expected_profit_usdc, realized, request.opportunity_id)
            self.position_watchdog.deregister_position(request.opportunity_id)


__all__ = [
    "CircuitBreakerState",
    "RiskLevel",
    "BreakerType",
    "CircuitBreakerEvent",
    "RiskSnapshot",
    "SpikeCheckResult",
    "SlippageCheck",
    "LimitCheck",
    "PositionRecord",
    "OverrideResult",
    "RiskCheckResult",
    "BreakerAnalytics",
    "GAS_SPIKE_THRESHOLD_PCT",
    "GAS_SPIKE_WINDOW_SECONDS",
    "MAX_SLIPPAGE_PCT",
    "BORROW_RATE_JUMP_THRESHOLD_PCT",
    "MAX_CONCURRENT_POSITIONS",
    "DAILY_LOSS_CAP_USDC",
    "MAX_COLLATERAL_RATIO",
    "MIN_COLLATERAL_RATIO",
    "POSITION_TIMEOUT_SECONDS",
    "HUMAN_OVERRIDE_WINDOW_SECONDS",
    "LARGE_TRADE_THRESHOLD_USDC",
    "RiskManager",
]