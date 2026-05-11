import time
from decimal import Decimal

from agent.risk_manager import BreakerType, RiskManager
from agent.execution_engine import ExecutionRequest
from compute.arbitrage_analyzer import InferenceOutput


def _build_request() -> ExecutionRequest:
    signal = InferenceOutput(
        opportunity_id="opp-risk-1",
        primary_dex="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount=Decimal("1000"),
        collateral_required=Decimal("1500"),
        expected_profit_usdc=Decimal("5"),
        risk_score=0.2,
        confidence=0.95,
        decision="EXECUTE",
        expiry_timestamp=int(time.time()) + 60,
        reasoning="integration test",
        model_version="v1.0",
        input_hash="hash-input",
        output_hash="hash-output",
        tee_signature="0x1234",
    )
    return ExecutionRequest(
        opportunity_id="opp-risk-1",
        decision_id="dec-risk-1",
        trace_id="trace-risk-1",
        signal=signal,
        primary_dex_router=signal.primary_dex,
        counter_dex_router=signal.counter_dex,
        borrow_amount_usdc=Decimal("1000"),
        collateral_amount_usdc=Decimal("1500"),
        min_profit_usdc=Decimal("1"),
        deadline=signal.expiry_timestamp,
        max_gas_price_gwei=100.0,
    )


def test_full_pre_execution_check_all_breakers_open(tmp_path):
    manager = RiskManager(web3=None, data_dir=str(tmp_path), auto_start=False)
    request = _build_request()

    for breaker_type in BreakerType:
        manager.registry.open_breaker(breaker_type, 1.0, request.opportunity_id, auto_reset_seconds=None, notes="test")

    result = manager.pre_execution_check(request)

    assert result.allowed is False
    assert set(result.blocking_breakers) == set(BreakerType)
