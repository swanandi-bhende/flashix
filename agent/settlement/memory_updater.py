from __future__ import annotations

from decimal import Decimal
from typing import Any, Tuple

from agent.agent_memory import FlashixMemory
from agent.settlement_monitor import ReceiptStatus, RevertReason, SettlementRecord


class AgentMemoryUpdater:
    def update_after_settlement(self, record: SettlementRecord, agent_memory: FlashixMemory, reasoning_trace: Any | None = None) -> None:
        narrative = ""
        if reasoning_trace is not None:
            narrative = getattr(getattr(reasoning_trace, "final_decision", None), "narrative", "")

        agent_memory.add_ai_message(
            f"DECISION MADE: Approved execution of {record.opportunity_id}. Expected profit: ${record.expected_profit_usdc:.4f} USDC. Reasoning: {narrative}"
        )

        gas_cost = record.gas_cost_usdc if record.gas_cost_usdc is not None else Decimal("0")
        settled_profit = record.realized_profit_usdc if record.realized_profit_usdc is not None else Decimal("0")
        revert_explanation = ""
        if record.receipt_status in {ReceiptStatus.REVERTED, ReceiptStatus.TIMEOUT, ReceiptStatus.DROPPED}:
            root_cause = getattr(getattr(record, "_postmortem_record", None), "root_cause", "unknown")
            revert_explanation = f" REVERT REASON: {record.revert_reason}. Root cause: {root_cause}."

        agent_memory.add_human_message(
            f"SETTLEMENT OUTCOME: {record.receipt_status.value}. Opportunity: {record.opportunity_id}. Realized profit: ${settled_profit:.4f} USDC. Variance: {record.profit_variance_pct or 0.0:.2f}%. Gas used: {record.gas_used or 0:,} units (${gas_cost:.4f}).{revert_explanation}"
        )

        if record.receipt_status in {ReceiptStatus.REVERTED, ReceiptStatus.TIMEOUT, ReceiptStatus.DROPPED} and record.revert_reason is not None:
            correction_message, adjustment_description = self.generate_correction_message(record.revert_reason, {})
            agent_memory.add_human_message(
                f"CORRECTION FOR FUTURE DECISIONS: The {record.revert_reason.value} failure indicates {correction_message}. For similar signals, apply adjustment: {adjustment_description}."
            )

    def generate_correction_message(self, revert_reason: RevertReason, decoded_args: dict[str, Any]) -> Tuple[str, str]:
        if revert_reason == RevertReason.PROFIT_BELOW_MINIMUM:
            actual = Decimal(str(decoded_args.get("actual_profit", 0)))
            minimum = Decimal(str(decoded_args.get("minimum_required", 0)))
            gap_pct = 0.0 if minimum == 0 else float(((minimum - actual) / minimum) * Decimal("100"))
            return "slippage was higher than estimated", f"increase slippage buffer by {gap_pct:.1f}%"
        if revert_reason == RevertReason.SIGNAL_EXPIRED:
            return "execution took too long after decision", "reduce reasoning timeout by 5 seconds"
        if revert_reason == RevertReason.SLIPPAGE_EXCEEDED:
            return "market moved more than the model allowed", "increase slippage tolerance"
        if revert_reason == RevertReason.INSUFFICIENT_COLLATERAL:
            return "collateral safety margins were too low", "increase collateral ratio threshold"
        if revert_reason == RevertReason.LENDING_POOL_INSUFFICIENT_LIQUIDITY:
            return "the borrow side was too large for current liquidity", "reduce maximum trade size"
        return "the decision gate missed a runtime constraint", "tighten the relevant risk limit"
