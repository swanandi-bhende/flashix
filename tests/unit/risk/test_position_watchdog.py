from decimal import Decimal
from unittest.mock import Mock

from agent.execution_engine import ExecutionEngine
from agent.risk.position_watchdog import PositionWatchdog
from agent.risk.risk_registry import RiskRegistry


def test_timeout_triggers_emergency_close(tmp_path, monkeypatch):
    registry = RiskRegistry(data_dir=str(tmp_path))
    watchdog = PositionWatchdog(registry=registry, auto_start=False)
    emergency_close = Mock()
    monkeypatch.setattr(ExecutionEngine, "emergency_close", emergency_close)

    monkeypatch.setattr("agent.risk.position_watchdog.time.time", lambda: 1000)
    watchdog.register_position("opp-timeout", "0xabc", Decimal("100"))

    monkeypatch.setattr("agent.risk.position_watchdog.time.time", lambda: 1031)
    watchdog._watchdog_iteration()

    emergency_close.assert_called_once_with("opp-timeout")
    assert "opp-timeout" in watchdog.timed_out_positions
