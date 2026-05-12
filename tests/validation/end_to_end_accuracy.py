from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

from tests.integration_test import AccuracyReport, DecisionAccuracyReport, FunnelReport, PipelineRunResult, TestOutcome


class EndToEndAccuracyValidator:
    def validate(self, results: list[PipelineRunResult]) -> AccuracyReport:
        executed = [result for result in results if str(getattr(result.settlement, "receipt_status", "")) == "ReceiptStatus.CONFIRMED" or str(getattr(result.settlement, "receipt_status", "")) == "CONFIRMED"]
        profit_errors: list[float] = []
        for result in executed:
            expected = float(getattr(result.opportunity, "expected_profit_usdc", 0.0) or 0.0)
            realized = float(getattr(result.settlement, "realized_profit_usdc", 0.0) or 0.0)
            if expected == 0:
                profit_errors.append(0.0 if realized == 0 else 100.0)
            else:
                profit_errors.append(abs(realized - expected) / abs(expected) * 100.0)

        if profit_errors:
            mean_error_pct = float(statistics.mean(profit_errors))
            median_error_pct = float(statistics.median(profit_errors))
            p95_error_pct = float(np.percentile(profit_errors, 95)) if np is not None else float(sorted(profit_errors)[max(0, int(round((len(profit_errors) - 1) * 0.95)))])
            pct_within_1pct = len([error for error in profit_errors if error <= 1.0]) / len(profit_errors)
            pct_within_5pct = len([error for error in profit_errors if error <= 5.0]) / len(profit_errors)
        else:
            mean_error_pct = median_error_pct = p95_error_pct = pct_within_1pct = pct_within_5pct = 0.0

        return AccuracyReport(
            executed_count=len(executed),
            mean_error_pct=mean_error_pct,
            median_error_pct=median_error_pct,
            p95_error_pct=p95_error_pct,
            pct_within_1pct=pct_within_1pct,
            pct_within_5pct=pct_within_5pct,
            profit_errors=profit_errors,
        )

    def validate_pipeline_decision_accuracy(self, results: list[PipelineRunResult]) -> DecisionAccuracyReport:
        true_positive = false_positive = true_negative = false_negative = 0
        for result in results:
            historical_outcome = getattr(result.opportunity, "historical_outcome", "UNKNOWN")
            executed = str(getattr(result.settlement, "receipt_status", "")) in {"ReceiptStatus.CONFIRMED", "CONFIRMED"}
            blocked = not executed
            if historical_outcome == "PROFITABLE" and executed:
                true_positive += 1
            elif historical_outcome == "PROFITABLE" and blocked:
                false_negative += 1
            elif historical_outcome != "PROFITABLE" and blocked:
                true_negative += 1
            elif historical_outcome != "PROFITABLE" and executed:
                false_positive += 1

        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return DecisionAccuracyReport(
            true_positive=true_positive,
            false_positive=false_positive,
            true_negative=true_negative,
            false_negative=false_negative,
            precision=precision,
            recall=recall,
            f1=f1,
        )

    def validate_rejection_funnel(self, results: list[PipelineRunResult]) -> FunnelReport:
        stage_rank = {
            "MEMPOOL_DETECTED": 1,
            "FILTER_PASSED": 2,
            "INFERENCE_PASSED": 3,
            "AGENT_PASSED": 4,
            "RISK_PASSED": 5,
            "EXECUTED": 6,
            "CONFIRMED": 7,
            "PROFITABLE": 8,
        }
        counts = {name: 0 for name in stage_rank}
        counts["MEMPOOL_DETECTED"] = len(results)

        for result in results:
            final_stage = str(getattr(result.trace, "final_stage", getattr(result.trace, "final_status", "")))
            current_rank = stage_rank.get(final_stage, 0)
            if current_rank >= 2:
                counts["FILTER_PASSED"] += 1
            if current_rank >= 3:
                counts["INFERENCE_PASSED"] += 1
            if current_rank >= 4:
                counts["AGENT_PASSED"] += 1
            if current_rank >= 5:
                counts["RISK_PASSED"] += 1
            if current_rank >= 6:
                counts["EXECUTED"] += 1
            if current_rank >= 7:
                counts["CONFIRMED"] += 1
            if current_rank >= 8:
                counts["PROFITABLE"] += 1

        return FunnelReport(
            detected=counts["MEMPOOL_DETECTED"],
            passed_filter=counts["FILTER_PASSED"],
            passed_inference=counts["INFERENCE_PASSED"],
            passed_agent=counts["AGENT_PASSED"],
            passed_risk=counts["RISK_PASSED"],
            executed=counts["EXECUTED"],
            confirmed=counts["CONFIRMED"],
            profitable=counts["PROFITABLE"],
        )
