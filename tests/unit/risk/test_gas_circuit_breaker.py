from collections import deque
from decimal import Decimal

from agent.risk.gas_circuit_breaker import GasCircuitBreaker
from agent.risk.risk_registry import RiskRegistry
from agent.risk_manager import BreakerType, CircuitBreakerState


def test_no_spike_below_threshold(tmp_path, monkeypatch):
    registry = RiskRegistry(data_dir=str(tmp_path))
    breaker = GasCircuitBreaker(registry=registry)
    breaker.samples = deque(((1000 + index, 20.0) for index in range(30)), maxlen=60)
    monkeypatch.setattr("agent.risk.gas_circuit_breaker.time.time", lambda: 1029)

    result = breaker.check_spike()

    assert result.spike_detected is False
    assert result.reason in {"NO_SPIKE", "INSUFFICIENT_HISTORY"}
    assert registry.breaker_states[BreakerType.GAS_SPIKE] == CircuitBreakerState.CLOSED


def test_spike_opens_breaker(tmp_path, monkeypatch):
    registry = RiskRegistry(data_dir=str(tmp_path))
    breaker = GasCircuitBreaker(registry=registry)
    breaker.samples = deque(
        [(1000 + index, 20.0 + (7.0 * index / 29.0)) for index in range(30)],
        maxlen=60,
    )
    monkeypatch.setattr("agent.risk.gas_circuit_breaker.time.time", lambda: 1029)

    result = breaker.check_spike()

    assert result.spike_detected is True
    assert result.spike_pct > 30.0
    assert result.baseline_fee_gwei == 20.0
    assert result.current_fee_gwei == 27.0
    assert registry.breaker_states[BreakerType.GAS_SPIKE] == CircuitBreakerState.OPEN


def test_auto_reset_after_normalization(tmp_path, monkeypatch):
    registry = RiskRegistry(data_dir=str(tmp_path))
    breaker = GasCircuitBreaker(registry=registry)
    monkeypatch.setattr("agent.risk.gas_circuit_breaker.time.time", lambda: 1000)
    registry.open_breaker(BreakerType.GAS_SPIKE, 35.0, None, auto_reset_seconds=60, notes="test")
    breaker.samples = deque(((1001 + index, 20.0) for index in range(60)), maxlen=60)

    monkeypatch.setattr("agent.risk.gas_circuit_breaker.time.time", lambda: 1061)

    breaker.check_auto_reset()

    assert registry.breaker_states[BreakerType.GAS_SPIKE] == CircuitBreakerState.CLOSED
