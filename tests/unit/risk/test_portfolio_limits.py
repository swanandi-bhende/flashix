from decimal import Decimal

from agent.risk.portfolio_limits import PortfolioLimitsEnforcer
from agent.risk.risk_registry import RiskRegistry
from agent.risk_manager import BreakerType, CircuitBreakerState


def test_third_position_allowed_fourth_blocked(tmp_path):
    registry = RiskRegistry(data_dir=str(tmp_path))
    enforcer = PortfolioLimitsEnforcer(registry=registry)

    enforcer.on_position_opened("opp-1")
    enforcer.on_position_opened("opp-2")
    enforcer.on_position_opened("opp-3")

    result = enforcer.check_concurrent_positions()

    assert result.allowed is False
    assert registry.breaker_states[BreakerType.MAX_CONCURRENT_POSITIONS] == CircuitBreakerState.OPEN


def test_daily_loss_cap_triggers_halt(tmp_path):
    registry = RiskRegistry(data_dir=str(tmp_path))
    enforcer = PortfolioLimitsEnforcer(registry=registry)

    enforcer.on_position_closed("opp-1", Decimal("-20"))
    enforcer.on_position_closed("opp-2", Decimal("-30"))

    assert registry.daily_pnl == Decimal("-50")
    assert registry.breaker_states[BreakerType.DAILY_LOSS_CAP] == CircuitBreakerState.OPEN


def test_midnight_reset_clears_daily_pnl(tmp_path, monkeypatch):
    registry = RiskRegistry(data_dir=str(tmp_path))
    enforcer = PortfolioLimitsEnforcer(registry=registry)
    registry.daily_pnl = Decimal("-60")
    registry.open_breaker(BreakerType.DAILY_LOSS_CAP, -60.0, None, auto_reset_seconds=None, notes="test")

    class FakeDatetime:
        @staticmethod
        def utcnow():
            return __import__("datetime").datetime(2026, 5, 11, 0, 0, 0)

    monkeypatch.setattr("agent.risk.portfolio_limits.datetime", FakeDatetime)

    enforcer._reset_daily_pnl_once(FakeDatetime.utcnow())

    assert registry.daily_pnl == Decimal("0")
    assert registry.breaker_states[BreakerType.DAILY_LOSS_CAP] == CircuitBreakerState.CLOSED
