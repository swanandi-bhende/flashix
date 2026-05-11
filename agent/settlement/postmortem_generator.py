from __future__ import annotations

import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any
from uuid import uuid4

from agent.market_data import AggregatedMarketState
from agent.settlement_monitor import FailureCategory, PostmortemRecord, ReceiptStatus, RevertDecodeResult, RevertReason, SettlementRecord

logger = logging.getLogger(__name__)


class PostmortemGenerator:
    def __init__(self, inference_recorder: Any = None) -> None:
        self.inference_recorder = inference_recorder

    def _flag_for_retraining(self, record: SettlementRecord) -> None:
        if self.inference_recorder is None:
            return
        if hasattr(self.inference_recorder, "flag_for_retraining"):
            self.inference_recorder.flag_for_retraining(record.opportunity_id)
            return
        if hasattr(self.inference_recorder, "update_ground_truth"):
            realized = record.realized_profit_usdc if record.realized_profit_usdc is not None else Decimal("0")
            self.inference_recorder.update_ground_truth(record.opportunity_id, realized, "UNPROFITABLE")

    def generate(
        self,
        record: SettlementRecord,
        revert_detail: RevertDecodeResult,
        reasoning_trace: Any,
        market_state_at_execution: AggregatedMarketState,
    ) -> PostmortemRecord:
        failure_category: FailureCategory = "UNKNOWN"
        root_cause = "Unknown failure"
        contributing_factors: list[str] = []
        risk_checks: list[str] = []
        recommended: dict[str, str] = {}

        if record.receipt_status == ReceiptStatus.REVERTED and revert_detail.reason == RevertReason.PROFIT_BELOW_MINIMUM:
            staleness = int(getattr(market_state_at_execution, "oldest_source_staleness_ms", 0))
            if staleness > 300:
                failure_category = "ORACLE_DATA_QUALITY"
                root_cause = "Stale oracle data caused profit overestimation"
                contributing_factors.append(f"Pyth staleness={staleness}ms at execution time")
                recommended = {"MAX_STALENESS_MS": "reduce from 500 to 300", "MIN_PROFIT_MARGIN_PERCENT": "increase by 0.5%"}
            else:
                failure_category = "MODEL_INACCURACY"
                root_cause = "Expected profit exceeded the realized profit after execution costs"
                recommended = {"MIN_PROFIT_MARGIN_PERCENT": "increase slightly"}
        elif record.receipt_status == ReceiptStatus.REVERTED and revert_detail.reason == RevertReason.SLIPPAGE_EXCEEDED:
            failure_category = "MODEL_INACCURACY"
            root_cause = "Slippage estimate was too optimistic"
            expected = record.expected_profit_usdc
            realized = record.realized_profit_usdc or Decimal("0")
            gap_pct = 0.0 if expected == 0 else float(((expected - realized) / expected) * Decimal("100"))
            recommended = {"SLIPPAGE_BUFFER_PCT": f"increase by {gap_pct:.1f}%"}
        elif record.receipt_status == ReceiptStatus.REVERTED and revert_detail.reason == RevertReason.SIGNAL_EXPIRED:
            failure_category = "RISK_CHECK_FAILURE"
            root_cause = "The execution was broadcast too long after the decision was made"
            time_from_decision_to_broadcast = int(record.execution_submit_ms - getattr(reasoning_trace, "created_at", record.execution_submit_ms))
            contributing_factors.append(f"decision_to_broadcast_ms={time_from_decision_to_broadcast}")
            if time_from_decision_to_broadcast > 20000:
                risk_checks = ["ApprovalGate should enforce max_decision_age < 20s"]
        elif record.receipt_status == ReceiptStatus.REVERTED and revert_detail.reason == RevertReason.INSUFFICIENT_COLLATERAL:
            failure_category = "RISK_CHECK_FAILURE"
            root_cause = "Collateral ratio was too low for safe execution"
            recommended = {"MIN_COLLATERAL_RATIO": "increase from 1.5 to 1.7"}
        elif record.receipt_status in {ReceiptStatus.TIMEOUT, ReceiptStatus.DROPPED}:
            failure_category = "RISK_CHECK_FAILURE"
            root_cause = f"Transaction ended with status {record.receipt_status.value} before confirmation"
            risk_checks = ["Receipt poller should enforce a tighter broadcast window"]

        variance_pct = record.profit_variance_pct or 0.0
        model_retraining_triggered = failure_category in {"MODEL_INACCURACY", "ORACLE_DATA_QUALITY"} and variance_pct > 5.0
        if model_retraining_triggered:
            try:
                self._flag_for_retraining(record)
            except Exception:
                logger.exception("SETTLEMENT_RETRAINING_FLAG_FAILED: opportunity_id=%s", record.opportunity_id)

        postmortem = PostmortemRecord(
            postmortem_id=str(uuid4()),
            settlement_record_id=record.record_id,
            opportunity_id=record.opportunity_id,
            failure_category=failure_category,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            risk_checks_that_should_have_caught_this=risk_checks,
            recommended_parameter_adjustments=recommended,
            model_retraining_triggered=model_retraining_triggered,
            generated_at=int(__import__("time").time() * 1000),
        )
        setattr(record, "_postmortem_record", postmortem)
        return postmortem
