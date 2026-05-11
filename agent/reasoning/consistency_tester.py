"""Consistency testing for structured reasoning traces."""

from __future__ import annotations

import re
from collections import Counter
from statistics import pstdev
from typing import List

from .cot_executor import ChainOfThoughtExecutor
from .market_stress import MarketConditions, MarketStressCalculator
from .schema import StabilityReport
from signal_processor import InferenceOutput


class ReasoningConsistencyTester:
    """Measure decision stability across repeated reasoning runs."""

    def __init__(self, executor: ChainOfThoughtExecutor | None = None) -> None:
        self.market_stress_calculator = MarketStressCalculator()
        self.executor = executor or ChainOfThoughtExecutor(dry_run_mode=True)

    def test_decision_stability(self, signal: InferenceOutput, n_runs: int = 10) -> StabilityReport:
        market_conditions = self.market_stress_calculator.build_market_conditions(
            signal.symbol,
            recent_trade_summary="Consistency test snapshot",
        )
        traces = [self.executor.execute(signal, market_conditions) for _ in range(n_runs)]
        decisions = [trace.final_decision.decision for trace in traces]
        decision_consistency_pct = 0.0
        if decisions:
            decision_consistency_pct = Counter(decisions).most_common(1)[0][1] / len(decisions) * 100.0

        profits = [float(trace.final_decision.expected_profit_usdc) for trace in traces]
        vix_scores = [float(trace.risk_assessment.vix_equivalent_score) for trace in traces]
        narrative_semantic_similarity = self._narrative_similarity(traces)

        return StabilityReport(
            decision_consistency_pct=round(decision_consistency_pct, 2),
            profit_estimate_std_dev=round(pstdev(profits), 4) if len(profits) > 1 else 0.0,
            vix_score_std_dev=round(pstdev(vix_scores), 4) if len(vix_scores) > 1 else 0.0,
            narrative_semantic_similarity=round(narrative_semantic_similarity, 2),
            run_count=n_runs,
            decisions=decisions,
            warnings=[],
        )

    def test_threshold_boundary_behavior(self) -> bool:
        boundary_cases = [
            (0.749, 1.99, "REJECT"),
            (0.751, 2.01, "APPROVE"),
        ] * 10
        all_passed = True
        market_conditions = MarketConditions(
            symbol="BTC",
            gas_price_gwei=0.0,
            gas_spike_detected=False,
            funding_rate_a=0.0,
            funding_rate_b=0.0,
            orderbook_depth_ratio=0.0,
            volatility_24h=0.0,
            vix_equivalent_score=10.0,
            funding_rate_volatility="LOW",
            execution_risk="LOW",
            liquidity_risk="LOW",
            gas_spike_risk="LOW",
            overall_risk="LOW",
            recent_trade_summary="Boundary test snapshot",
        )
        for index, (confidence, target_profit, expected_decision) in enumerate(boundary_cases):
            signal = self._build_boundary_signal(index, confidence, target_profit)
            trace = self.executor.execute(signal, market_conditions)
            if trace.final_decision.decision != expected_decision:
                all_passed = False
        return all_passed

    def generate_consistency_report(self) -> str:
        signal = self._build_boundary_signal(999, 0.751, 2.01)
        stability_report = self.test_decision_stability(signal, n_runs=10)
        boundary_ok = self.test_threshold_boundary_behavior()
        stability_status = "PASS" if stability_report.decision_consistency_pct >= 90.0 else "FAIL"
        profit_status = "PASS" if stability_report.profit_estimate_std_dev < 0.10 else "FAIL"
        vix_status = "PASS" if stability_report.vix_score_std_dev < 2.0 else "FAIL"
        similarity_status = "PASS" if stability_report.narrative_semantic_similarity >= 95.0 else "FAIL"
        boundary_status = "PASS" if boundary_ok else "FAIL"

        return (
            "# Reasoning Consistency Report\n\n"
            "## Summary\n"
            f"- Decision consistency: {stability_report.decision_consistency_pct:.2f}% ({stability_status})\n"
            f"- Profit std dev: {stability_report.profit_estimate_std_dev:.4f} ({profit_status})\n"
            f"- VIX std dev: {stability_report.vix_score_std_dev:.4f} ({vix_status})\n"
            f"- Narrative similarity: {stability_report.narrative_semantic_similarity:.2f}% ({similarity_status})\n"
            f"- Boundary behavior: {boundary_status}\n\n"
            "## Notes\n"
            "- Consistency is evaluated on a fixed market snapshot.\n"
            "- Boundary checks cover confidence thresholds and $2.00 profit boundaries.\n"
        )

    def _build_boundary_signal(self, index: int, confidence: float, target_profit: float) -> InferenceOutput:
        spread_usdc = target_profit + 2.9
        price_a = 100.0
        price_b = price_a * (1.0 + spread_usdc / 1000.0)
        return InferenceOutput(
            opportunity_id=f"boundary_{index}_{confidence}_{target_profit}",
            symbol="BTC",
            primary_dex="Hyperliquid",
            counter_dex="dYdX",
            price_a=price_a,
            price_b=price_b,
            gross_spread_percent=0.0,
            borrow_amount=1000.0,
            collateral_required=0.0,
            expected_profit_usdc=target_profit,
            confidence=confidence,
            risk_score=0.2,
            expiry_timestamp=9999999999,
            decision="EXECUTE",
            tee_signature="sig_" + "f" * 64,
            model_version="arbitrage_scorer_v1",
        )

    def _narrative_similarity(self, traces: List[object]) -> float:
        if len(traces) < 2:
            return 100.0
        signatures = []
        for trace in traces:
            sections = [
                trace.opportunity_analysis.narrative,
                trace.cost_breakdown.narrative,
                trace.profit_calculation.narrative,
                trace.risk_assessment.narrative,
                trace.final_decision.narrative,
            ]
            signatures.append(tuple(self._extract_numbers(section) for section in sections))
        return 100.0 if len({str(signature) for signature in signatures}) == 1 else 0.0

    def _extract_numbers(self, text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"-?\d+(?:\.\d+)?", text))
