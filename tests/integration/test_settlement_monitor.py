from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from web3 import Web3

from agent.agent_memory import FlashixMemory
from agent.execution_engine import ExecutionRequest, ExecutionResult
from agent.reasoning.schema import ReasoningTrace
from agent.settlement.ledger import SettlementLedger
from agent.settlement.memory_updater import AgentMemoryUpdater
from agent.settlement.postmortem_generator import PostmortemGenerator
from agent.settlement.profit_analyzer import ProfitVarianceAnalyzer
from agent.settlement.receipt_poller import ReceiptPoller
from agent.settlement.revert_decoder import RevertDecoder
from agent.settlement_monitor import (
    ArbitrageExecutedEvent,
    DecodedLogs,
    FlashLoanRepaidEvent,
    PollingResult,
    ReceiptStatus,
    RevertDecodeResult,
    RevertReason,
    SettlementMonitor,
    SettlementRecord,
)
from compute.arbitrage_analyzer import InferenceOutput
from tests.replay.inference_recorder import InferenceRecorder


W3 = Web3()


def _bytes32_from_text(text: str) -> bytes:
    return text.encode("utf-8").ljust(32, b"\0")[:32]


def _trace_payload() -> dict:
    return {
        "trace_id": "trace-123",
        "opportunity_id": "opp-123",
        "opportunity_analysis": {
            "price_dex_a": "100.0",
            "price_dex_b": "101.0",
            "long_dex": "DEX_A",
            "short_dex": "DEX_B",
            "gross_spread_usdc": "20",
            "gross_spread_percent": "2.0",
            "borrow_amount_usdc": "1000",
            "signal_confidence": 0.95,
            "signal_expiry_seconds": 30,
            "narrative": "Strong spread",
        },
        "cost_breakdown": {
            "flashloan_fee_pct": "0.09",
            "flashloan_fee_usdc": "0.9",
            "slippage_estimate_pct": "0.2",
            "slippage_estimate_usdc": "2.0",
            "collateral_rate_pct_per_day": "0.01",
            "collateral_cost_usdc": "0.1",
            "gas_price_gwei": 20.0,
            "gas_cost_usdc": "5.0",
            "total_cost_pct": "0.5",
            "total_cost_usdc": "8.0",
            "narrative": "Low gas",
        },
        "profit_calculation": {
            "gross_spread_pct": "2.0",
            "total_cost_pct": "0.5",
            "net_profit_pct": "1.5",
            "net_profit_usdc": "12.0",
            "profit_after_gas_usdc": "11.0",
            "break_even_spread_pct": "0.5",
            "narrative": "Positive net profit",
        },
        "risk_assessment": {
            "vix_equivalent_score": 25.0,
            "funding_rate_volatility": "LOW",
            "execution_risk": "LOW",
            "liquidity_risk": "LOW",
            "gas_spike_risk": "LOW",
            "overall_risk": "LOW",
            "risk_factors": ["normal gas"],
            "mitigating_factors": ["deep liquidity"],
            "narrative": "Low risk",
        },
        "final_decision": {
            "decision": "APPROVE",
            "rejection_reason": None,
            "expected_profit_usdc": "12.0",
            "expected_execution_time_seconds": 5,
            "decision_confidence": 0.98,
            "conditions": ["normal"],
            "narrative": "Approved because spread is robust.",
        },
        "total_reasoning_ms": 120.0,
        "gemini_tokens_used": 100,
        "created_at": int(time.time() * 1000) - 1000,
        "model_version": "test-model",
    }


def _build_trace() -> ReasoningTrace:
    return ReasoningTrace.from_payload(_trace_payload())


def _build_request() -> ExecutionRequest:
    signal = InferenceOutput(
        opportunity_id="opp-123",
        primary_dex="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount=Decimal("1000"),
        collateral_required=Decimal("1500"),
        expected_profit_usdc=Decimal("12.0"),
        risk_score=0.2,
        confidence=0.98,
        decision="EXECUTE",
        expiry_timestamp=int(time.time()) + 60,
        reasoning="Strong arbitrage signal",
        model_version="v1.0",
        input_hash="input-hash",
        output_hash="output-hash",
        tee_signature="sig",
    )
    return ExecutionRequest(
        opportunity_id="opp-123",
        decision_id="dec-123",
        trace_id="trace-123",
        signal=signal,
        primary_dex_router="0x1111111254fb6c44bac0bed2854e76f90643097d",
        counter_dex_router="0x3fC91A3afd70395Cd496C647d5a6CC533d562e63",
        borrow_amount_usdc=Decimal("1000"),
        collateral_amount_usdc=Decimal("1500"),
        min_profit_usdc=Decimal("10"),
        deadline=signal.expiry_timestamp,
        max_gas_price_gwei=100.0,
        simulation_required=True,
    )


def _encode_topic(type_name: str, value: object) -> bytes:
    return W3.codec.encode([type_name], [value])


def _build_success_receipt(tx_hash: str = "0xabc123") -> dict:
    opportunity_id = _bytes32_from_text("opp-123")
    signal_id = opportunity_id
    dex_a = Web3.to_checksum_address("0x1111111254fb6c44bac0bed2854e76f90643097d")
    dex_b = Web3.to_checksum_address("0x3fC91A3afd70395Cd496C647d5a6CC533d562e63")
    receiver = Web3.to_checksum_address("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    token = Web3.to_checksum_address("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    signer = Web3.to_checksum_address("0xcccccccccccccccccccccccccccccccccccccccc")
    arb_sig = Web3.keccak(text="ArbitrageExecuted(bytes32,address,address,uint256,uint256)")
    flash_sig = Web3.keccak(text="FlashLoanExecuted(address,address,uint256,uint256)")
    verified_sig = Web3.keccak(text="SignalVerified(bytes32,address)")

    logs = [
        {
            "address": "0x0000000000000000000000000000000000000001",
            "topics": [verified_sig, _encode_topic("bytes32", opportunity_id), _encode_topic("address", signer)],
            "data": b"",
            "logIndex": 0,
            "transactionHash": tx_hash,
            "blockNumber": 123,
        },
        {
            "address": "0x0000000000000000000000000000000000000002",
            "topics": [arb_sig, _encode_topic("bytes32", signal_id), _encode_topic("address", dex_a), _encode_topic("address", dex_b)],
            "data": W3.codec.encode(["uint256", "uint256"], [12_500_000, 185_000]),
            "logIndex": 1,
            "transactionHash": tx_hash,
            "blockNumber": 123,
        },
        {
            "address": "0x0000000000000000000000000000000000000003",
            "topics": [flash_sig, _encode_topic("address", receiver), _encode_topic("address", token)],
            "data": W3.codec.encode(["uint256", "uint256"], [1_000_000_000, 900_000]),
            "logIndex": 2,
            "transactionHash": tx_hash,
            "blockNumber": 123,
        },
    ]
    return {
        "transactionHash": tx_hash,
        "blockNumber": 123,
        "gasUsed": 185_000,
        "status": 1,
        "logs": logs,
    }


def _build_timeout_record() -> SettlementRecord:
    return SettlementRecord(
        record_id="record-timeout",
        opportunity_id="opp-timeout",
        correlation_id="corr-timeout",
        decision_id="dec-timeout",
        trace_id="trace-timeout",
        tx_hash="0xtimeout",
        block_number=None,
        block_timestamp=None,
        receipt_status=ReceiptStatus.TIMEOUT,
        revert_reason=None,
        revert_raw_bytes=None,
        gas_limit=200000,
        gas_used=None,
        gas_efficiency_pct=None,
        effective_gas_price_gwei=None,
        gas_cost_usdc=None,
        expected_profit_usdc=Decimal("10"),
        realized_profit_usdc=None,
        profit_variance_usdc=None,
        profit_variance_pct=None,
        repayment_confirmed=None,
        execution_submit_ms=int(time.time() * 1000) - 5000,
        first_seen_in_mempool_ms=None,
        confirmed_at_ms=None,
        total_execution_latency_ms=None,
        confirmation_latency_ms=None,
        polling_attempts=0,
        settled_at=int(time.time() * 1000),
    )


@pytest.fixture
def temp_ledger(tmp_path: Path) -> SettlementLedger:
    return SettlementLedger(db_path=tmp_path / "flashix.db")


def test_successful_settlement_extracts_correct_profit(tmp_path: Path):
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    poller = MagicMock()
    poller.poll = MagicMock(return_value=PollingResult(status=ReceiptStatus.CONFIRMED, attempt=3, poll_start_ms=int(time.time() * 1000) - 2000, latency_ms=150, receipt=_build_success_receipt()))

    monitor = SettlementMonitor(
        ledger=ledger,
        poller=poller,
        revert_decoder=RevertDecoder(web3=W3),
        agent_memory=FlashixMemory(),
        risk_manager=MagicMock(),
        redis_client=MagicMock(),
    )

    record = monitor.monitor(SimpleNamespace(tx_hash="0xabc123", gas_limit=250000, execution_submit_ms=int(time.time() * 1000) - 4000), _build_request(), _build_trace())

    assert record.realized_profit_usdc is not None and record.realized_profit_usdc > Decimal("0")
    assert record.repayment_confirmed is True
    assert record.receipt_status == ReceiptStatus.CONFIRMED


def test_revert_reason_decoded_profit_below_minimum(tmp_path: Path):
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    poller = MagicMock()
    poller.poll = MagicMock(return_value=PollingResult(status=ReceiptStatus.REVERTED, attempt=2, poll_start_ms=int(time.time() * 1000) - 1000, latency_ms=100, receipt={"transactionHash": "0xdead", "blockNumber": 123, "status": 0, "logs": []}))

    monitor = SettlementMonitor(
        ledger=ledger,
        poller=poller,
        revert_decoder=MagicMock(decode=MagicMock(return_value=RevertDecodeResult(RevertReason.PROFIT_BELOW_MINIMUM, "profit below minimum", {"actual_profit": 9500000, "minimum_required": 10000000}, "0x08c379a0"))),
        agent_memory=FlashixMemory(),
        market_state_provider=lambda: SimpleNamespace(oldest_source_staleness_ms=100),
        risk_manager=MagicMock(),
        redis_client=MagicMock(),
    )

    record = monitor.monitor(SimpleNamespace(tx_hash="0xdead", gas_limit=250000, execution_submit_ms=int(time.time() * 1000) - 4000), _build_request(), _build_trace())

    assert record.revert_reason == RevertReason.PROFIT_BELOW_MINIMUM
    assert getattr(record, "_postmortem_record").failure_category == "MODEL_INACCURACY"


def test_timeout_creates_ledger_record(tmp_path: Path):
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    poller = MagicMock()
    poller.poll = MagicMock(return_value=PollingResult(status=ReceiptStatus.TIMEOUT, attempt=8, poll_start_ms=int(time.time() * 1000) - 7000, latency_ms=None, receipt=None))

    monitor = SettlementMonitor(
        ledger=ledger,
        poller=poller,
        agent_memory=FlashixMemory(),
        risk_manager=MagicMock(),
        redis_client=MagicMock(),
    )

    record = monitor.monitor(SimpleNamespace(tx_hash="0xtimeout", gas_limit=200000, execution_submit_ms=int(time.time() * 1000) - 6000), _build_request(), _build_trace())

    records = ledger.get_records_payload()
    assert records[0]["receipt_status"] == "TIMEOUT"
    assert records[0]["realized_profit_usdc"] is None
    assert record.receipt_status == ReceiptStatus.TIMEOUT


def test_memory_updated_with_outcome(tmp_path: Path):
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    agent_memory = FlashixMemory()
    poller = MagicMock()
    poller.poll = MagicMock(return_value=PollingResult(status=ReceiptStatus.CONFIRMED, attempt=1, poll_start_ms=int(time.time() * 1000) - 1000, latency_ms=100, receipt=_build_success_receipt()))

    monitor = SettlementMonitor(
        ledger=ledger,
        poller=poller,
        agent_memory=agent_memory,
        risk_manager=MagicMock(),
        redis_client=MagicMock(),
    )

    monitor.monitor(SimpleNamespace(tx_hash="0xabc123", gas_limit=250000, execution_submit_ms=int(time.time() * 1000) - 2000), _build_request(), _build_trace())

    last_human = [message for message in agent_memory.get_messages() if message["type"] == "human"][-1]["content"]
    assert "opp-123" in last_human
    assert "USDC" in last_human


def test_systematic_bias_detected_after_10_overestimates(temp_ledger: SettlementLedger):
    for index in range(10):
        record = _build_timeout_record()
        record.record_id = f"record-{index}"
        record.opportunity_id = f"opp-{index}"
        record.receipt_status = ReceiptStatus.CONFIRMED
        record.realized_profit_usdc = Decimal("96.5")
        record.expected_profit_usdc = Decimal("100")
        record.profit_variance_pct = -3.5
        record.profit_variance_usdc = Decimal("-3.5")
        record.settled_at += index
        temp_ledger.insert(record)

    analyzer = ProfitVarianceAnalyzer(temp_ledger)
    bias_report = analyzer.compute_rolling_bias()

    assert bias_report.mean_variance_pct < -2.0
    assert "tighten MIN_PROFIT_MARGIN" in bias_report.recommendation


def test_postmortem_triggers_model_retraining_flag(tmp_path: Path):
    recorder = InferenceRecorder(db_path=tmp_path / "inference_replay.db")
    generator = PostmortemGenerator(inference_recorder=recorder)
    record = _build_timeout_record()
    record.receipt_status = ReceiptStatus.REVERTED
    record.revert_reason = RevertReason.PROFIT_BELOW_MINIMUM
    record.profit_variance_pct = 6.0
    record.realized_profit_usdc = Decimal("106")
    market_state = SimpleNamespace(oldest_source_staleness_ms=100)

    postmortem = generator.generate(record, RevertDecodeResult(RevertReason.PROFIT_BELOW_MINIMUM, "profit below minimum", {"actual_profit": 9500000, "minimum_required": 10000000}, "0x00"), _build_trace(), market_state)
    recorder.flush()

    assert postmortem.model_retraining_triggered is True
    with recorder._conn:
        row = recorder._conn.execute("SELECT ground_truth_status FROM inference_records WHERE correlation_id = ?", (record.opportunity_id,)).fetchone()
    assert row[0] == "UNPROFITABLE"
    recorder.close()


def test_receipt_poller_detects_drop():
    web3 = MagicMock()
    web3.eth.get_transaction_receipt.side_effect = Exception("not mined")
    web3.eth.get_transaction.return_value = None
    web3.eth.get_block.return_value = {"timestamp": int(time.time())}
    poller = ReceiptPoller(web3=web3)

    result = asyncio.run(poller.poll("0xdropped", max_wait_seconds=1))

    assert result.status == ReceiptStatus.DROPPED


def test_ledger_stats_aggregates_counts_and_pnl(temp_ledger: SettlementLedger):
    confirmed = _build_timeout_record()
    confirmed.record_id = "record-confirmed"
    confirmed.opportunity_id = "opp-confirmed"
    confirmed.receipt_status = ReceiptStatus.CONFIRMED
    confirmed.realized_profit_usdc = Decimal("12.5")
    confirmed.gas_cost_usdc = Decimal("2.5")
    confirmed.gas_efficiency_pct = 75.0
    confirmed.confirmation_latency_ms = 100
    confirmed.settled_at = int(time.time() * 1000)
    temp_ledger.insert(confirmed)

    reverted = _build_timeout_record()
    reverted.record_id = "record-reverted"
    reverted.opportunity_id = "opp-reverted"
    reverted.receipt_status = ReceiptStatus.REVERTED
    reverted.revert_reason = RevertReason.SLIPPAGE_EXCEEDED
    reverted.settled_at = int(time.time() * 1000) + 1
    temp_ledger.insert(reverted)

    stats = temp_ledger.get_ledger_stats()

    assert stats.total_executions == 2
    assert stats.confirmed_count == 1
    assert stats.reverted_count == 1
    assert stats.net_pnl_usdc == Decimal("10.0")
