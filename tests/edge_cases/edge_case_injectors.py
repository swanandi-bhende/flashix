from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from agent.risk_manager import MIN_COLLATERAL_RATIO
from tests.integration_test import TestCaseResult, TestOutcome, now_ms
from tests.simulation.pipeline_harness import PipelineHarness
from tests.integration_test import SimulatedOpportunity


class EdgeCaseInjector:
    def _make_result(self, test_id: str, test_name: str, scenario_type: str, outcome: TestOutcome, expected_behavior: str, actual_behavior: str, failures: list[str], latency_ms: float, notes: str) -> TestCaseResult:
        return TestCaseResult(
            test_id=test_id,
            test_name=test_name,
            scenario_type=scenario_type,
            outcome=outcome,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            assertion_failures=failures,
            execution_latency_ms=latency_ms,
            notes=notes,
        )

    def _base_opportunity(self, edge_case_type: str, symbol: str = "BTC-USD-PERP") -> SimulatedOpportunity:
        return SimulatedOpportunity(
            id=f"edge-{edge_case_type.lower()}-{now_ms()}",
            symbol=symbol,
            dex_a="hyperliquid",
            dex_b="dydx",
            price_a=104.0,
            price_b=100.0,
            gross_spread_pct=4.0,
            funding_rate_a=0.0001,
            funding_rate_b=0.00005,
            gas_price_gwei=30.0,
            timestamp=now_ms(),
            expected_duration_minutes=3,
            historical_outcome="PROFITABLE",
            expected_profit_usdc=100.0,
            gap_ms=0,
            scenario_type=edge_case_type,
            edge_case_type=edge_case_type,
            collateral_ratio=1.6,
            market_state={"edge_case": edge_case_type},
        )

    def inject_liquidation_scenario(self, harness: PipelineHarness) -> TestCaseResult:
        harness.mock_blockchain.set_collateral_ratio(0.90)
        opp = self._base_opportunity("LIQUIDATION_SCENARIO")
        result = harness.run_opportunity(opp)
        passed = getattr(result.settlement, "final_status", "") == "BLOCKED_BY_RISK" and not getattr(result.settlement, "tx_hash", "")
        return self._make_result(
            test_id=opp.id,
            test_name="liquidation_scenario",
            scenario_type="LIQUIDATION_SCENARIO",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Risk manager blocks execution when collateral drops below 1.5x",
            actual_behavior=getattr(result.settlement, "final_status", result.status),
            failures=[] if passed else ["expected BLOCKED_BY_RISK with no transaction"],
            latency_ms=result.wall_clock_latency_ms,
            notes="Collateral ratio forced to 0.90.",
        )

    def inject_funding_rate_spike(self, harness: PipelineHarness) -> TestCaseResult:
        harness.market_data_service.override_funding_rate("BTC-USD-PERP", 0.009)
        opp = self._base_opportunity("FUNDING_RATE_SPIKE")
        result = harness.run_opportunity(opp)
        passed = getattr(result.settlement, "final_status", "") in {"BLOCKED_BY_GAS", "BLOCKED_BY_RISK"}
        return self._make_result(
            test_id=opp.id,
            test_name="funding_rate_spike",
            scenario_type="FUNDING_RATE_SPIKE",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Borrow-rate circuit breaker opens quickly and prevents execution",
            actual_behavior=getattr(result.settlement, "final_status", result.status),
            failures=[] if passed else ["expected breaker-triggered block"],
            latency_ms=result.wall_clock_latency_ms,
            notes="Funding rate overridden to 0.009.",
        )

    def inject_network_delay_mild(self, harness: PipelineHarness, delay_ms: int = 3000) -> TestCaseResult:
        harness.mock_blockchain.set_delay_ms(delay_ms)
        opp = self._base_opportunity("NETWORK_DELAY_MILD")
        result = harness.run_opportunity(opp)
        passed = getattr(result.settlement, "final_status", "") != "TIMEOUT" and result.wall_clock_latency_ms < 30_000.0
        return self._make_result(
            test_id=opp.id,
            test_name="network_delay_mild",
            scenario_type="NETWORK_DELAY_MILD",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Execution completes inside the watchdog window despite modest network delay",
            actual_behavior=getattr(result.settlement, "final_status", result.status),
            failures=[] if passed else ["expected completion without timeout"],
            latency_ms=result.wall_clock_latency_ms,
            notes=f"Simulated delay {delay_ms}ms.",
        )

    def inject_network_delay_severe(self, harness: PipelineHarness, delay_ms: int = 35_000) -> TestCaseResult:
        harness.mock_blockchain.set_delay_ms(delay_ms)
        opp = self._base_opportunity("NETWORK_DELAY_SEVERE")
        result = harness.run_opportunity(opp)
        passed = getattr(result.settlement, "final_status", "") == "TIMEOUT" and getattr(result.settlement, "receipt_status", None).name == "TIMEOUT"
        return self._make_result(
            test_id=opp.id,
            test_name="network_delay_severe",
            scenario_type="NETWORK_DELAY_SEVERE",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Watchdog closes the position and marks the settlement as TIMEOUT",
            actual_behavior=getattr(result.settlement, "final_status", result.status),
            failures=[] if passed else ["expected TIMEOUT settlement"],
            latency_ms=result.wall_clock_latency_ms,
            notes=f"Simulated delay {delay_ms}ms.",
        )

    def inject_model_drift_early(self, harness: PipelineHarness) -> TestCaseResult:
        harness.mock_tee_client.set_model_drift(2.0)
        harness.mock_blockchain.set_profit_penalty_pct(2.0)
        opportunities = [self._base_opportunity("MODEL_DRIFT_EARLY", symbol="BTC-USD-PERP") for _ in range(20)]
        results = [harness.run_opportunity(opportunity) for opportunity in opportunities]
        original_records = list(harness.settlement_records)
        try:
            harness.settlement_records[:] = [result.settlement for result in results]
            bias = harness.profit_analyzer.compute_rolling_bias(lookback_n=20)
        finally:
            harness.settlement_records[:] = original_records
            harness.mock_blockchain.set_profit_penalty_pct(0.0)
        passed = bias.mean_variance_pct < -1.5
        return self._make_result(
            test_id=opportunities[0].id,
            test_name="model_drift_early",
            scenario_type="MODEL_DRIFT_EARLY",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Rolling variance bias becomes materially negative when the model is stale",
            actual_behavior=f"mean_variance_pct={bias.mean_variance_pct:.2f}",
            failures=[] if passed else ["expected mean_variance_pct < -1.5"],
            latency_ms=sum(result.wall_clock_latency_ms for result in results),
            notes="Applied +2.0% model drift bias.",
        )

    def inject_gas_spike(self, harness: PipelineHarness, spike_pct: float = 40.0) -> TestCaseResult:
        harness.market_data_service.set_gas_price(harness.market_data_service.baseline_gas_price_gwei * 1.4)
        harness.mock_blockchain.set_gas_spike_pct(spike_pct)
        opps = [self._base_opportunity("GAS_SPIKE") for _ in range(5)]
        results = [harness.run_opportunity(opportunity) for opportunity in opps]
        passed = all(getattr(result.settlement, "final_status", "") == "BLOCKED_BY_GAS" for result in results)
        return self._make_result(
            test_id=opps[0].id,
            test_name="gas_spike",
            scenario_type="GAS_SPIKE",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Gas circuit breaker opens and blocks all five opportunities",
            actual_behavior=", ".join(getattr(result.settlement, "final_status", result.status) for result in results),
            failures=[] if passed else ["expected all results to be BLOCKED_BY_GAS"],
            latency_ms=sum(result.wall_clock_latency_ms for result in results),
            notes=f"Gas spike forced to {spike_pct:.1f}%.",
        )

    def inject_flash_crash(self, harness: PipelineHarness) -> TestCaseResult:
        harness.market_data_service.override_price("BTC-USD-PERP", 80.0)
        opps = [self._base_opportunity("FLASH_CRASH") for _ in range(3)]
        results = [harness.run_opportunity(opportunity) for opportunity in opps]
        passed = all(getattr(result.settlement, "final_status", "") == "SKIP" for result in results)
        return self._make_result(
            test_id=opps[0].id,
            test_name="flash_crash",
            scenario_type="FLASH_CRASH",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Inference module skips all flash-crash opportunities",
            actual_behavior=", ".join(getattr(result.settlement, "final_status", result.status) for result in results),
            failures=[] if passed else ["expected SKIP decisions from inference"],
            latency_ms=sum(result.wall_clock_latency_ms for result in results),
            notes="One DEX price reduced to 80% of prior level.",
        )

    def inject_collateral_drop_10pct(self, harness: PipelineHarness) -> TestCaseResult:
        harness.mock_blockchain.set_collateral_ratio(1.44)
        opp = self._base_opportunity("COLLATERAL_DROP_10PCT")
        result = harness.run_opportunity(opp)
        passed = getattr(result.settlement, "final_status", "") == "BLOCKED_BY_RISK" and getattr(result.settlement, "receipt_status", None).name != "CONFIRMED"
        return self._make_result(
            test_id=opp.id,
            test_name="collateral_drop_10pct",
            scenario_type="COLLATERAL_DROP_10PCT",
            outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
            expected_behavior="Position closes before collateral falls under the 1.5x floor",
            actual_behavior=getattr(result.settlement, "final_status", result.status),
            failures=[] if passed else ["expected pre-emptive risk close before MIN_COLLATERAL_RATIO"],
            latency_ms=result.wall_clock_latency_ms,
            notes=f"Collateral ratio reduced from 1.6x to 1.44x; floor={MIN_COLLATERAL_RATIO}.",
        )
