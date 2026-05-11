from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from agent.market_data import AggregatedMarketState, DataQualityLevel
from agent.reasoning.schema import ReasoningTrace
from agent.agent_memory import FlashixMemory

logger = logging.getLogger(__name__)


class ReceiptStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REVERTED = "REVERTED"
    TIMEOUT = "TIMEOUT"
    DROPPED = "DROPPED"


class RevertReason(str, Enum):
    INVALID_SIGNAL_SIGNATURE = "INVALID_SIGNAL_SIGNATURE"
    SIGNAL_ALREADY_USED = "SIGNAL_ALREADY_USED"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    PROFIT_BELOW_MINIMUM = "PROFIT_BELOW_MINIMUM"
    INSUFFICIENT_COLLATERAL = "INSUFFICIENT_COLLATERAL"
    SLIPPAGE_EXCEEDED = "SLIPPAGE_EXCEEDED"
    LENDING_POOL_INSUFFICIENT_LIQUIDITY = "LENDING_POOL_INSUFFICIENT_LIQUIDITY"
    REPAYMENT_FAILED = "REPAYMENT_FAILED"
    UNKNOWN_REVERT = "UNKNOWN_REVERT"
    DECODE_FAILED = "DECODE_FAILED"


FailureCategory = Literal[
    "RISK_CHECK_FAILURE",
    "MODEL_INACCURACY",
    "MARKET_CONDITION_CHANGE",
    "ORACLE_DATA_QUALITY",
    "GAS_ESTIMATION_ERROR",
    "SMART_CONTRACT_LOGIC",
    "UNKNOWN",
]


@dataclass(frozen=True)
class RawLog:
    address: str
    topics: list[str]
    data: str
    log_index: Optional[int] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None


@dataclass(frozen=True)
class PollingResult:
    status: ReceiptStatus
    attempt: int
    poll_start_ms: int
    latency_ms: Optional[int] = None
    receipt: Any = None


@dataclass(frozen=True)
class FlashLoanInitiatedEvent:
    borrower: str
    token: str
    amount: int
    fee: int
    initiated_at: int


@dataclass(frozen=True)
class SignalVerifiedEvent:
    opportunity_id: bytes
    signer: str
    verified_at: int


@dataclass(frozen=True)
class ArbitrageExecutedEvent:
    signal_id: bytes
    dex_a: str
    dex_b: str
    profit_realized: int
    gas_used: int
    timestamp: int


@dataclass(frozen=True)
class FlashLoanRepaidEvent:
    borrower: str
    token: str
    amount: int
    fee: int
    repaid_at: int


@dataclass
class DecodedLogs:
    flash_loan_initiated: Optional[FlashLoanInitiatedEvent] = None
    signal_verified: Optional[SignalVerifiedEvent] = None
    arbitrage_executed: Optional[ArbitrageExecutedEvent] = None
    flash_loan_repaid: Optional[FlashLoanRepaidEvent] = None
    unrecognized_logs: list[RawLog] = field(default_factory=list)


@dataclass(frozen=True)
class RepaymentVerification:
    confirmed: bool
    expected_repayment: Decimal
    actual_repayment: Decimal
    delta_wei: Decimal
    explanation: str


@dataclass(frozen=True)
class RevertDecodeResult:
    reason: RevertReason
    human_message: str
    decoded_args: dict[str, Any] = field(default_factory=dict)
    raw_bytes: Optional[str] = None


@dataclass(frozen=True)
class ProfitVarianceAnalysis:
    expected_usdc: Decimal
    realized_usdc: Decimal
    variance_usdc: Decimal
    variance_pct: float
    variance_direction: Literal["OVERESTIMATED", "UNDERESTIMATED", "ACCURATE"]
    primary_variance_driver: str


@dataclass(frozen=True)
class HighVarianceCondition:
    condition_description: str
    mean_variance_pct: float
    sample_count: int
    recommended_action: str


@dataclass(frozen=True)
class BiasReport:
    mean_variance_pct: float
    median_variance_pct: float
    sample_count: int
    classification: str
    recommendation: str


@dataclass(frozen=True)
class LedgerStats:
    total_executions: int
    confirmed_count: int
    reverted_count: int
    timeout_count: int
    total_realized_profit_usdc: Decimal
    total_gas_cost_usdc: Decimal
    net_pnl_usdc: Decimal
    avg_gas_efficiency_pct: float
    avg_confirmation_latency_ms: float
    revert_rate_pct: float
    most_common_revert_reason: Optional[RevertReason]


@dataclass
class SettlementRecord:
    record_id: str
    opportunity_id: str
    correlation_id: str
    decision_id: str
    trace_id: str
    tx_hash: str
    block_number: Optional[int]
    block_timestamp: Optional[int]
    receipt_status: ReceiptStatus
    revert_reason: Optional[RevertReason]
    revert_raw_bytes: Optional[str]
    gas_limit: int
    gas_used: Optional[int]
    gas_efficiency_pct: Optional[float]
    effective_gas_price_gwei: Optional[float]
    gas_cost_usdc: Optional[Decimal]
    expected_profit_usdc: Decimal
    realized_profit_usdc: Optional[Decimal]
    profit_variance_usdc: Optional[Decimal]
    profit_variance_pct: Optional[float]
    repayment_confirmed: Optional[bool]
    execution_submit_ms: int
    first_seen_in_mempool_ms: Optional[int]
    confirmed_at_ms: Optional[int]
    total_execution_latency_ms: Optional[int]
    confirmation_latency_ms: Optional[int]
    polling_attempts: int
    settled_at: int

    def touch(self) -> None:
        self.settled_at = int(time.time() * 1000)


@dataclass(frozen=True)
class PostmortemRecord:
    postmortem_id: str
    settlement_record_id: str
    opportunity_id: str
    failure_category: FailureCategory
    root_cause: str
    contributing_factors: list[str]
    risk_checks_that_should_have_caught_this: list[str]
    recommended_parameter_adjustments: dict[str, str]
    model_retraining_triggered: bool
    generated_at: int


def _now_ms() -> int:
    return int(time.time() * 1000)


class SettlementMonitor:
    def __init__(
        self,
        web3: Any = None,
        ledger: Any = None,
        poller: Any = None,
        log_decoder: Any = None,
        revert_decoder: Any = None,
        profit_analyzer: Any = None,
        memory_updater: Any = None,
        postmortem_generator: Any = None,
        agent_memory: Optional[FlashixMemory] = None,
        risk_manager: Any = None,
        inference_recorder: Any = None,
        market_state_provider: Optional[Callable[[], AggregatedMarketState]] = None,
        redis_client: Any = None,
    ) -> None:
        from agent.settlement.ledger import SettlementLedger
        from agent.settlement.log_decoder import TransactionLogDecoder
        from agent.settlement.memory_updater import AgentMemoryUpdater
        from agent.settlement.postmortem_generator import PostmortemGenerator
        from agent.settlement.profit_analyzer import ProfitVarianceAnalyzer
        from agent.settlement.receipt_poller import ReceiptPoller
        from agent.settlement.revert_decoder import RevertDecoder

        self.web3 = web3
        self.ledger = ledger or SettlementLedger(web3=web3)
        self.poller = poller or ReceiptPoller(web3=web3)
        self.log_decoder = log_decoder or TransactionLogDecoder(web3=web3)
        self.revert_decoder = revert_decoder or RevertDecoder(web3=web3)
        self.profit_analyzer = profit_analyzer or ProfitVarianceAnalyzer(self.ledger)
        self.memory_updater = memory_updater or AgentMemoryUpdater()
        self.postmortem_generator = postmortem_generator or PostmortemGenerator(inference_recorder=inference_recorder)
        self.agent_memory = agent_memory or FlashixMemory()
        self.risk_manager = risk_manager
        self.inference_recorder = inference_recorder
        self.market_state_provider = market_state_provider
        self.redis_client = redis_client

    def monitor(self, execution_result: Any, request: Any, reasoning_trace: ReasoningTrace) -> SettlementRecord:
        return asyncio.run(self._monitor_async(execution_result, request, reasoning_trace))

    async def _monitor_async(self, execution_result: Any, request: Any, reasoning_trace: ReasoningTrace) -> SettlementRecord:
        poll_start_ms = _now_ms()
        correlation_id = getattr(execution_result, "correlation_id", None) or getattr(request, "correlation_id", None) or request.opportunity_id
        tx_hash = str(execution_result.tx_hash)
        receipt_result = PollingResult(status=ReceiptStatus.PENDING, attempt=0, poll_start_ms=poll_start_ms)

        try:
            poll_result = self.poller.poll(tx_hash, max_wait_seconds=60)
            receipt_result = await poll_result if hasattr(poll_result, "__await__") else poll_result
        except Exception:
            logger.exception("SETTLEMENT_POLL_FAILED: tx_hash=%s", tx_hash)
            receipt_result = PollingResult(status=ReceiptStatus.TIMEOUT, attempt=0, poll_start_ms=poll_start_ms)

        record = SettlementRecord(
            record_id=str(uuid4()),
            opportunity_id=request.opportunity_id,
            correlation_id=correlation_id,
            decision_id=request.decision_id,
            trace_id=request.trace_id,
            tx_hash=tx_hash,
            block_number=getattr(receipt_result.receipt, "blockNumber", None),
            block_timestamp=None,
            receipt_status=receipt_result.status,
            revert_reason=None,
            revert_raw_bytes=None,
            gas_limit=int(getattr(execution_result, "gas_limit", getattr(request, "gas_limit", 0)) or 0),
            gas_used=getattr(receipt_result.receipt, "gasUsed", None),
            gas_efficiency_pct=None,
            effective_gas_price_gwei=None,
            gas_cost_usdc=None,
            expected_profit_usdc=Decimal(str(request.signal.expected_profit_usdc)),
            realized_profit_usdc=None,
            profit_variance_usdc=None,
            profit_variance_pct=None,
            repayment_confirmed=None,
            execution_submit_ms=int(getattr(execution_result, "execution_submit_ms", poll_start_ms)),
            first_seen_in_mempool_ms=getattr(execution_result, "first_seen_in_mempool_ms", None),
            confirmed_at_ms=receipt_result.poll_start_ms + (receipt_result.latency_ms or 0) if receipt_result.status == ReceiptStatus.CONFIRMED else None,
            total_execution_latency_ms=getattr(execution_result, "execution_latency_ms", None),
            confirmation_latency_ms=receipt_result.latency_ms,
            polling_attempts=receipt_result.attempt,
            settled_at=_now_ms(),
        )
        setattr(record, "market_vix_score", float(getattr(reasoning_trace.risk_assessment, "vix_equivalent_score", 0.0)))
        setattr(record, "position_size_usdc", Decimal(str(getattr(request, "borrow_amount_usdc", record.expected_profit_usdc))))

        decoded_logs = DecodedLogs()
        revert_detail = RevertDecodeResult(reason=RevertReason.UNKNOWN_REVERT, human_message="No revert detail available")
        realized_profit: Optional[Decimal] = None
        repayment_confirmed: Optional[bool] = None

        if receipt_result.status == ReceiptStatus.CONFIRMED and receipt_result.receipt is not None:
            try:
                decoded_logs = self.log_decoder.decode_all_logs(receipt_result.receipt)
                realized_profit = self.log_decoder.extract_realized_profit(decoded_logs)
                if decoded_logs.flash_loan_repaid is not None:
                    borrow_amount_usdc = Decimal(str(getattr(request, "borrow_amount_usdc", Decimal("0"))))
                    expected_repayment = borrow_amount_usdc * (Decimal("1") + Decimal("0.0009")) * Decimal(10**6)
                    repayment = self.log_decoder.verify_repayment(decoded_logs, expected_repayment)
                    repayment_confirmed = repayment.confirmed
            except Exception:
                logger.exception("SETTLEMENT_LOG_DECODE_FAILED: tx_hash=%s", tx_hash)

        if receipt_result.status == ReceiptStatus.REVERTED and receipt_result.receipt is not None:
            try:
                revert_detail = self.revert_decoder.decode(receipt_result.receipt)
                decoded_logs = self.log_decoder.decode_all_logs(receipt_result.receipt)
                if revert_detail.raw_bytes:
                    record.revert_raw_bytes = revert_detail.raw_bytes
            except Exception:
                logger.exception("SETTLEMENT_REVERT_DECODE_FAILED: tx_hash=%s", tx_hash)

        if receipt_result.status in {ReceiptStatus.CONFIRMED, ReceiptStatus.REVERTED}:
            if realized_profit is None:
                realized_profit = Decimal("0") if receipt_result.status == ReceiptStatus.REVERTED else None
            if receipt_result.status == ReceiptStatus.CONFIRMED:
                try:
                    analysis = self.profit_analyzer.analyze(Decimal(str(request.signal.expected_profit_usdc)), realized_profit or Decimal("0"), record)
                    record.profit_variance_usdc = analysis.variance_usdc
                    record.profit_variance_pct = analysis.variance_pct
                    record.realized_profit_usdc = realized_profit
                except Exception:
                    logger.exception("SETTLEMENT_VARIANCE_ANALYSIS_FAILED: tx_hash=%s", tx_hash)

        if receipt_result.status in {ReceiptStatus.REVERTED, ReceiptStatus.TIMEOUT, ReceiptStatus.DROPPED}:
            if receipt_result.status == ReceiptStatus.REVERTED:
                record.revert_reason = revert_detail.reason
                record.revert_raw_bytes = revert_detail.raw_bytes
            try:
                market_state = self.market_state_provider() if self.market_state_provider else self._default_market_state(reasoning_trace)
                postmortem = self.postmortem_generator.generate(record, revert_detail, reasoning_trace, market_state)
                setattr(record, "_postmortem_record", postmortem)
            except Exception:
                logger.exception("SETTLEMENT_POSTMORTEM_FAILED: opportunity_id=%s", record.opportunity_id)

        if receipt_result.status == ReceiptStatus.CONFIRMED:
            record.repayment_confirmed = repayment_confirmed
            record.realized_profit_usdc = realized_profit
            if record.realized_profit_usdc is not None:
                record.profit_variance_usdc = record.realized_profit_usdc - record.expected_profit_usdc
                if record.expected_profit_usdc != 0:
                    record.profit_variance_pct = float((record.profit_variance_usdc / record.expected_profit_usdc) * Decimal("100"))
            try:
                if self.memory_updater:
                    self.memory_updater.update_after_settlement(record, self.agent_memory, reasoning_trace)
            except Exception:
                logger.exception("SETTLEMENT_MEMORY_UPDATE_FAILED: opportunity_id=%s", record.opportunity_id)

        try:
            self.ledger.insert(record)
        except Exception:
            logger.exception("SETTLEMENT_LEDGER_INSERT_FAILED: opportunity_id=%s", record.opportunity_id)

        try:
            if receipt_result.status in {ReceiptStatus.REVERTED, ReceiptStatus.TIMEOUT, ReceiptStatus.DROPPED}:
                postmortem = getattr(record, "_postmortem_record", None)
                if postmortem is not None:
                    self.ledger.insert_postmortem(postmortem)
        except Exception:
            logger.exception("SETTLEMENT_POSTMORTEM_INSERT_FAILED: opportunity_id=%s", record.opportunity_id)

        try:
            if self.redis_client is not None:
                self.redis_client.hset(
                    f"flashix:correlation:{correlation_id}",
                    mapping={"final_status": record.receipt_status.value, "total_latency_ms": int((record.confirmed_at_ms or _now_ms()) - record.execution_submit_ms)},
                )
        except Exception:
            logger.exception("SETTLEMENT_REDIS_UPDATE_FAILED: correlation_id=%s", correlation_id)

        try:
            if self.risk_manager is not None and hasattr(self.risk_manager, "post_execution_update"):
                self.risk_manager.post_execution_update(execution_result, request)
        except Exception:
            logger.exception("SETTLEMENT_RISK_UPDATE_FAILED: opportunity_id=%s", record.opportunity_id)

        return record

    def _default_market_state(self, reasoning_trace: ReasoningTrace) -> AggregatedMarketState:
        return AggregatedMarketState(
            symbol=getattr(reasoning_trace.opportunity_analysis, "symbol", "UNKNOWN"),
            consensus_price=Decimal("0"),
            price_std_dev=Decimal("0"),
            max_deviation_pct=0.0,
            funding_rate_consensus=Decimal("0"),
            collateral_ratio_consensus=Decimal("0"),
            sources_used=[],
            sources_failed=[],
            data_quality=DataQualityLevel.UNAVAILABLE,
            aggregated_at_ms=_now_ms(),
            oldest_source_staleness_ms=0,
        )


__all__ = [
    "ArbitrageExecutedEvent",
    "BiasReport",
    "DecodedLogs",
    "FailureCategory",
    "FlashLoanInitiatedEvent",
    "FlashLoanRepaidEvent",
    "HighVarianceCondition",
    "LedgerStats",
    "PollingResult",
    "PostmortemRecord",
    "ProfitVarianceAnalysis",
    "RawLog",
    "ReceiptStatus",
    "RepaymentVerification",
    "RevertDecodeResult",
    "RevertReason",
    "SettlementMonitor",
    "SettlementRecord",
    "SignalVerifiedEvent",
]