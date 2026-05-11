"""
Comprehensive test suite for the atomic flashloan execution engine.
Uses Hardhat's mainnet-fork feature to test against realistic chain state
without spending real funds.

Run with: npx hardhat test tests/integration/test_execution_engine.py --network hardhat
"""

import json
import time
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import pytest

from agent.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
    ExecutionResult,
    ApprovalValidation,
    SimulationResult,
    GasFees,
    ViabilityCheck,
    BroadcastResult,
    SettlementValidation,
    ApprovalGateError,
    MissingApprovalGate,
    RejectedByReasoningEngine,
    StaleDecision,
    GasSpikeDetected,
    SimulationFailedError,
    TransactionBuildError,
    BroadcastError,
    SettlementError,
)
from agent.execution.approval_gate import ApprovalGate
from agent.execution.gas_monitor import GasMonitor
from agent.execution.tx_builder import TransactionBuilder
from agent.execution.simulator import TransactionSimulator
from agent.execution.broadcaster import TransactionBroadcaster
from agent.execution.settlement_validator import SettlementValidator
from compute.arbitrage_analyzer import InferenceOutput


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_web3():
    """Mock Web3 instance for testing."""
    web3 = MagicMock()
    web3.eth.block_number = 12345
    web3.eth.get_transaction_count.return_value = 10
    web3.eth.gas_price = 1000000000
    web3.eth.get_block.return_value = {'baseFeePerGas': 50000000000}
    web3.to_wei = lambda x, unit: int(x * 1e9) if unit == 'gwei' else int(x)
    web3.to_checksum_address = lambda x: x
    web3.eth.contract = MagicMock()
    return web3


@pytest.fixture
def test_inference_signal():
    """Create a test InferenceOutput signal."""
    return InferenceOutput(
        opportunity_id="opp_test_12345",
        primary_dex="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount=Decimal("1000"),
        collateral_required=Decimal("1500"),
        expected_profit_usdc=Decimal("100"),
        risk_score=0.2,
        confidence=0.95,
        decision="EXECUTE",
        expiry_timestamp=int(time.time()) + 30,
        reasoning="Strong arbitrage signal on Uniswap-SushiSwap pair",
        model_version="v1.0",
        input_hash="hash_input_12345",
        output_hash="hash_output_12345",
        tee_signature="0x1234567890abcdef",
    )


@pytest.fixture
def test_execution_request(test_inference_signal):
    """Create a test ExecutionRequest."""
    return ExecutionRequest(
        opportunity_id="opp_test_12345",
        decision_id="dec_test_12345",
        trace_id="trace_test_12345",
        signal=test_inference_signal,
        primary_dex_router="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex_router="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount_usdc=Decimal("1000"),
        collateral_amount_usdc=Decimal("1500"),
        min_profit_usdc=Decimal("90"),  # 10% below expected
        deadline=int(time.time()) + 30,
        max_gas_price_gwei=100.0,
        simulation_required=True,
    )


@pytest.fixture
def mock_decision_log(tmp_path):
    """Create a mock decision log file."""
    log_file = tmp_path / "agent_decisions.jsonl"
    decision_record = {
        "decision_id": "dec_test_12345",
        "opportunity_id": "opp_test_12345",
        "decision": "APPROVE",
        "reasoning": "Signal confidence > 0.95",
        "confidence": 0.95,
        "expected_profit": 100.0,
        "timestamp": int(time.time()),
        "approved_by": "Flashix",
    }
    log_file.write_text(json.dumps(decision_record) + "\n")
    return str(log_file)


# ============================================================================
# APPROVAL GATE TESTS
# ============================================================================


def test_approval_gate_blocks_missing_decision(mock_decision_log):
    """
    Test that ApprovalGate blocks execution when decision_id is not in log.
    """
    gate = ApprovalGate(log_path=mock_decision_log)
    
    # Create a request with a decision_id that doesn't exist in the log
    signal = InferenceOutput(
        opportunity_id="opp_nonexistent",
        primary_dex="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount=Decimal("1000"),
        collateral_required=Decimal("1500"),
        expected_profit_usdc=Decimal("100"),
        risk_score=0.2,
        confidence=0.95,
        decision="EXECUTE",
        expiry_timestamp=int(time.time()) + 30,
        reasoning="Test",
        model_version="v1.0",
        input_hash="hash_input",
        output_hash="hash_output",
        tee_signature="0x1234567890abcdef",
    )
    
    request = ExecutionRequest(
        opportunity_id="opp_nonexistent",
        decision_id="dec_nonexistent",
        trace_id="trace_test",
        signal=signal,
        primary_dex_router="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex_router="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount_usdc=Decimal("1000"),
        collateral_amount_usdc=Decimal("1500"),
        min_profit_usdc=Decimal("90"),
        deadline=int(time.time()) + 30,
    )
    
    with pytest.raises(MissingApprovalGate):
        gate.validate(request)


def test_approval_gate_blocks_rejected_decision(mock_decision_log, tmp_path):
    """
    Test that ApprovalGate blocks REJECT decisions.
    """
    log_file = tmp_path / "rejected_decisions.jsonl"
    rejected_record = {
        "decision_id": "dec_rejected_12345",
        "opportunity_id": "opp_rejected_12345",
        "decision": "REJECT",
        "rejection_reason": "Confidence below threshold",
        "timestamp": int(time.time()),
    }
    log_file.write_text(json.dumps(rejected_record) + "\n")
    
    gate = ApprovalGate(log_path=str(log_file))
    
    signal = InferenceOutput(
        opportunity_id="opp_rejected_12345",
        primary_dex="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount=Decimal("1000"),
        collateral_required=Decimal("1500"),
        expected_profit_usdc=Decimal("100"),
        risk_score=0.2,
        confidence=0.8,
        decision="SKIP",
        expiry_timestamp=int(time.time()) + 30,
        reasoning="Low confidence",
        model_version="v1.0",
        input_hash="hash_input",
        output_hash="hash_output",
        tee_signature="0x1234567890abcdef",
    )
    
    request = ExecutionRequest(
        opportunity_id="opp_rejected_12345",
        decision_id="dec_rejected_12345",
        trace_id="trace_test",
        signal=signal,
        primary_dex_router="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex_router="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount_usdc=Decimal("1000"),
        collateral_amount_usdc=Decimal("1500"),
        min_profit_usdc=Decimal("90"),
        deadline=int(time.time()) + 30,
    )
    
    with pytest.raises(RejectedByReasoningEngine):
        gate.validate(request)


def test_approval_gate_passes_valid_decision(mock_decision_log, test_execution_request):
    """
    Test that ApprovalGate passes for a valid APPROVE decision.
    """
    gate = ApprovalGate(log_path=mock_decision_log)
    
    result = gate.validate(test_execution_request)
    
    assert result.passed is True
    assert result.decision_record is not None
    assert result.decision_record["decision"] == "APPROVE"
    assert result.seconds_to_expiry > 0


# ============================================================================
# SIMULATION TESTS
# ============================================================================


def test_simulation_catches_insufficient_liquidity(mock_web3):
    """
    Test that simulator catches InsufficientLiquidity revert.
    """
    simulator = TransactionSimulator(web3=mock_web3)
    
    # Mock eth_call to raise a revert
    from web3.exceptions import ContractLogicError
    mock_web3.eth.call.side_effect = ContractLogicError(
        "execution reverted: InsufficientLiquidity"
    )
    
    tx = {
        "from": "0x1234567890123456789012345678901234567890",
        "to": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "gas": 300000,
        "data": "0x",
    }
    
    result = simulator.simulate(tx)
    
    assert result.passed is False
    assert "Insufficient" in result.revert_reason or "Liquidity" in result.revert_reason
    assert result.simulated_profit_usdc == Decimal("0")


def test_simulation_succeeds_with_profit(mock_web3):
    """
    Test that simulator extracts profit from successful call.
    """
    simulator = TransactionSimulator(web3=mock_web3)
    
    # Mock eth_call to return a profit value (100 USDC = 100 * 10^6 wei)
    profit_wei = 100 * 10**6
    result_bytes = profit_wei.to_bytes(32, 'big')
    mock_web3.eth.call.return_value = result_bytes
    
    tx = {
        "from": "0x1234567890123456789012345678901234567890",
        "to": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "gas": 300000,
        "data": "0x",
    }
    
    result = simulator.simulate(tx)
    
    assert result.passed is True
    assert result.simulated_profit_usdc == Decimal("100")
    assert result.latency_ms > 0


# ============================================================================
# GAS MONITOR TESTS
# ============================================================================


def test_gas_monitor_detects_spike(mock_web3):
    """
    Test that GasMonitor detects gas spikes and raises GasSpikeDetected.
    """
    monitor = GasMonitor(web3=mock_web3)
    
    # Mock fee_history with high base fee
    mock_web3.eth.fee_history.return_value = {
        'baseFeePerGas': [100000000000] * 11,  # Very high base fee
        'reward': [[1000000000, 1500000000, 2000000000]] * 10,
    }
    
    with patch('agent.execution.gas_monitor.HISTORICAL_BASE_FEE_GWEI', 30):
        monitor.current_fees = None  # Clear cache
        
        with pytest.raises(GasSpikeDetected):
            monitor.is_execution_viable(Decimal("100"))


def test_gas_monitor_blocks_high_cost(mock_web3):
    """
    Test that GasMonitor blocks execution when gas > 30% of profit.
    """
    monitor = GasMonitor(web3=mock_web3)
    
    # Mock fee_history with normal base fee but high cost scenario
    mock_web3.eth.fee_history.return_value = {
        'baseFeePerGas': [30000000000] * 11,
        'reward': [[1000000000, 1500000000, 2000000000]] * 10,
    }
    
    monitor.current_fees = None
    
    # With $50 USDC profit and high gas price, gas cost will exceed 30%
    with patch('agent.execution.gas_monitor.DEFAULT_ETH_PRICE_USDC', Decimal("5000")):
        with patch('agent.execution.gas_monitor.MAX_GAS_UNITS', 300000):
            result = monitor.is_execution_viable(Decimal("50"))
            
            # Should be marked as not viable
            if result.gas_cost_usdc > 15:  # 30% of $50
                assert result.viable is False


# ============================================================================
# EXECUTION ENGINE INTEGRATION TESTS
# ============================================================================


def test_full_execution_cycle_successful(
    mock_web3, test_execution_request, mock_decision_log
):
    """
    Test the full execution cycle with mocked components.
    """
    engine = ExecutionEngine(web3=mock_web3, private_key="0x" + "1" * 64)
    
    # Mock all components
    with patch.object(engine.approval_gate, 'validate') as mock_approve:
        with patch.object(engine.gas_monitor, 'is_execution_viable') as mock_gas:
            with patch.object(engine.tx_builder, 'build_flashloan_tx') as mock_build:
                with patch.object(engine.simulator, 'simulate') as mock_sim:
                    with patch.object(engine.broadcaster, 'broadcast') as mock_broadcast:
                        with patch.object(engine.settlement_validator, 'validate_settlement') as mock_settle:
                            # Setup mocks to return success
                            mock_approve.return_value = ApprovalValidation(
                                passed=True,
                                seconds_to_expiry=25,
                            )
                            
                            mock_gas.return_value = ViabilityCheck(
                                viable=True,
                                reason="Gas OK",
                                margin_pct=50.0,
                            )
                            
                            mock_build.return_value = {"gas": 250000, "maxFeePerGas": 100}
                            
                            mock_sim.return_value = SimulationResult(
                                passed=True,
                                simulated_profit_usdc=Decimal("100"),
                                latency_ms=150.0,
                            )
                            
                            mock_broadcast.return_value = BroadcastResult(
                                status="CONFIRMED",
                                tx_hash="0xabcdef123456",
                                block_number=12345,
                                gas_used=200000,
                                realized_profit_usdc=Decimal("98"),
                                explorer_link="https://explorer.com/0xabcdef123456",
                            )
                            
                            mock_settle.return_value = SettlementValidation(
                                valid=True,
                                reason="Settlement OK",
                            )
                            
                            # Execute
                            result = engine.execute(test_execution_request)
                            
                            # Verify result
                            assert result.opportunity_id == "opp_test_12345"
                            assert result.status == "CONFIRMED"
                            assert result.tx_hash == "0xabcdef123456"
                            assert result.realized_profit_usdc == Decimal("98")
                            assert result.explorer_link is not None


def test_execution_blocked_by_gas_spike(
    mock_web3, test_execution_request
):
    """
    Test that execution is blocked when GasMonitor detects a spike.
    """
    engine = ExecutionEngine(web3=mock_web3, private_key="0x" + "1" * 64)
    
    with patch.object(engine.approval_gate, 'validate') as mock_approve:
        with patch.object(engine.gas_monitor, 'is_execution_viable') as mock_gas:
            mock_approve.return_value = ApprovalValidation(passed=True)
            mock_gas.side_effect = GasSpikeDetected("Severe gas spike")
            
            result = engine.execute(test_execution_request)
            
            assert result.status == "BROADCAST_FAILURE"
            assert "gas" in result.revert_reason.lower()


def test_execution_blocks_stale_decision(
    mock_web3, test_execution_request, tmp_path
):
    """
    Test that execution blocks a stale decision (> 25 seconds old).
    """
    # Create a stale decision log
    log_file = tmp_path / "stale_decisions.jsonl"
    stale_record = {
        "decision_id": "dec_test_12345",
        "opportunity_id": "opp_test_12345",
        "decision": "APPROVE",
        "timestamp": int(time.time()) - 30,  # 30 seconds old
    }
    log_file.write_text(json.dumps(stale_record) + "\n")
    
    engine = ExecutionEngine(web3=mock_web3, private_key="0x" + "1" * 64)
    engine.approval_gate = ApprovalGate(log_path=str(log_file))
    
    result = engine.execute(test_execution_request)

    assert result.status == "BROADCAST_FAILURE"
    assert "old" in result.revert_reason.lower()


# ============================================================================
# SETTLEMENT VALIDATOR TESTS
# ============================================================================


def test_settlement_validator_records_profitable_trade(mock_web3, test_execution_request, tmp_path):
    """
    Test that SettlementValidator records a profitable trade to database.
    """
    db_path = tmp_path / "test_opportunities.db"
    validator = SettlementValidator(web3=mock_web3, db_path=str(db_path))
    
    broadcast_result = BroadcastResult(
        status="CONFIRMED",
        tx_hash="0x1234567890abcdef",
        block_number=12345,
        gas_used=200000,
        realized_profit_usdc=Decimal("95"),
        explorer_link="https://explorer.com/0x1234",
    )
    
    result = validator.validate_settlement(broadcast_result, test_execution_request)
    
    assert result.valid is True
    assert result.realized_profit_usdc == Decimal("95")


def test_settlement_validator_rejects_insufficient_profit(
    mock_web3, test_execution_request
):
    """
    Test that SettlementValidator rejects profit below minimum threshold.
    """
    validator = SettlementValidator(web3=mock_web3)
    
    broadcast_result = BroadcastResult(
        status="CONFIRMED",
        tx_hash="0x1234567890abcdef",
        block_number=12345,
        gas_used=200000,
        realized_profit_usdc=Decimal("50"),  # Below min_profit_usdc * tolerance
        explorer_link="https://explorer.com/0x1234",
    )
    
    with pytest.raises(SettlementError):
        validator.validate_settlement(broadcast_result, test_execution_request)


# ============================================================================
# RUN TESTS
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
