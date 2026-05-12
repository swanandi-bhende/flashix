from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TEE_SIGNING_KEY", "1" * 64)

from tests.edge_cases.edge_case_injectors import EdgeCaseInjector
from tests.integration_test import (
    AccuracyReport,
    DeploymentGateValidator,
    IntegrationTestReport,
    TestCaseResult,
    TestOutcome,
    TestSessionConfig,
    dump_report,
    now_ms,
)
from tests.simulation.opportunity_simulator import OpportunitySimulator
from tests.simulation.pipeline_harness import PipelineHarness
from tests.data.historical_loader import HistoricalDataLoader
from tests.validation.end_to_end_accuracy import EndToEndAccuracyValidator
from tests.validation.latency_profiler import LatencyProfiler


def _build_session_config(args: argparse.Namespace) -> TestSessionConfig:
    return TestSessionConfig(
        session_id=f"integration-{now_ms()}",
        data_source=args.data_source,
        n_opportunities=args.n_opportunities,
        pipeline_mode="FULL",
        dry_run_mode=True,
        tee_mode="simulation",
        time_acceleration_factor=args.time_acceleration,
        random_seed=args.seed,
        edge_case_injection_enabled=True,
        edge_case_types=[
            "LIQUIDATION_SCENARIO",
            "FUNDING_RATE_SPIKE",
            "NETWORK_DELAY_MILD",
            "NETWORK_DELAY_SEVERE",
            "GAS_SPIKE",
            "MODEL_DRIFT_EARLY",
            "MODEL_DRIFT_LATE",
            "ZERO_LIQUIDITY",
            "FLASH_CRASH",
            "COLLATERAL_DROP_10PCT",
        ],
        max_execution_time_seconds=600,
    )


def _opportunity_to_case(result: Any) -> TestCaseResult:
    opportunity = result.opportunity
    settlement = result.settlement
    historical = getattr(opportunity, "historical_outcome", "UNKNOWN")
    final_status = getattr(settlement, "final_status", getattr(result, "status", "UNKNOWN"))
    expected_behavior = "Execute profitably" if historical == "PROFITABLE" else "Block or skip"
    actual_behavior = f"{final_status} / realized={getattr(settlement, 'realized_profit_usdc', None)}"
    failures: list[str] = []
    outcome = TestOutcome.PASS

    if historical == "PROFITABLE":
        if final_status == "CONFIRMED":
            expected = float(getattr(opportunity, "expected_profit_usdc", 0.0) or 0.0)
            realized = float(getattr(settlement, "realized_profit_usdc", 0.0) or 0.0)
            error_pct = 0.0 if expected == 0 else abs(realized - expected) / abs(expected) * 100.0
            if error_pct > 5.0:
                outcome = TestOutcome.FAIL
                failures.append(f"profit error {error_pct:.2f}% exceeds 5%")
        else:
            outcome = TestOutcome.FAIL
            failures.append("historically profitable opportunity was not executed")
    else:
        if final_status == "CONFIRMED":
            outcome = TestOutcome.FAIL
            failures.append("historically unprofitable opportunity was executed")

    if final_status in {"TIMEOUT", "BLOCKED_BY_RISK", "BLOCKED_BY_GAS"} and historical == "PROFITABLE":
        outcome = TestOutcome.FAIL
        failures.append(f"safety block on profitable opportunity: {final_status}")

    return TestCaseResult(
        test_id=opportunity.id,
        test_name=f"replay_{opportunity.id}",
        scenario_type=getattr(opportunity, "scenario_type", "HISTORICAL_REPLAY"),
        outcome=outcome,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        assertion_failures=failures,
        execution_latency_ms=float(getattr(result, "wall_clock_latency_ms", 0.0)),
        notes=getattr(settlement, "final_status", final_status),
    )


def _reset_harness_state(harness: PipelineHarness) -> None:
    harness.mock_blockchain.set_delay_ms(0)
    harness.mock_blockchain.set_gas_spike_pct(0.0)
    harness.mock_blockchain.set_profit_penalty_pct(0.0)
    harness.mock_blockchain.set_collateral_ratio(1.6)
    harness.market_data_service.set_gas_price(harness.market_data_service.baseline_gas_price_gwei)
    harness.market_data_service.set_collateral_ratio(1.6)
    harness.market_data_service.data_quality = harness.market_data_service.data_quality.__class__.HIGH
    harness.mock_tee_client.set_model_drift(0.0)


def _load_dataset(config: TestSessionConfig) -> Any:
    loader = HistoricalDataLoader()
    if config.data_source == "SYNTHETIC":
        return loader.generate_synthetic_fallback(n_days=7)

    fixture = loader.fixture_path
    if fixture.exists():
        try:
            return loader.load_from_fixture(fixture)
        except Exception:
            pass

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    try:
        return loader.fetch_historical_data(start.isoformat(), end.isoformat(), ["BTC-USD-PERP", "ETH-USD-PERP", "SOL-USD-PERP"])
    except Exception:
        return loader.generate_synthetic_fallback(n_days=7)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Flashix integration tests")
    parser.add_argument("--n-opportunities", type=int, default=120)
    parser.add_argument("--data-source", choices=["SYNTHETIC", "HISTORICAL_REPLAY", "HYBRID"], default="HYBRID")
    parser.add_argument("--time-acceleration", type=float, default=50.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-report", type=str, default="docs/integration_reports/latest.json")
    args = parser.parse_args(argv)

    config = _build_session_config(args)
    loader_dataset = _load_dataset(config)
    simulator = OpportunitySimulator()
    opportunities = simulator.generate_opportunities(loader_dataset, n_target=max(0, config.n_opportunities - 20))
    if config.edge_case_injection_enabled:
        opportunities = simulator.inject_edge_cases(opportunities)

    harness = PipelineHarness(config)
    results = harness.run_all(opportunities)

    accuracy_validator = EndToEndAccuracyValidator()
    latency_profiler = LatencyProfiler()
    accuracy_report = accuracy_validator.validate(results)
    decision_accuracy = accuracy_validator.validate_pipeline_decision_accuracy(results)
    funnel_report = accuracy_validator.validate_rejection_funnel(results)
    latency_profile = latency_profiler.profile(results)
    latency_markdown = latency_profiler.generate_latency_report_markdown(latency_profile)

    injector = EdgeCaseInjector()
    edge_results = []
    edge_results.append(injector.inject_liquidation_scenario(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_funding_rate_spike(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_network_delay_mild(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_network_delay_severe(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_model_drift_early(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_gas_spike(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_flash_crash(harness))
    _reset_harness_state(harness)
    edge_results.append(injector.inject_collateral_drop_10pct(harness))
    _reset_harness_state(harness)

    test_case_results = [_opportunity_to_case(result) for result in results] + edge_results
    passed = sum(1 for result in test_case_results if result.outcome == TestOutcome.PASS)
    failed = sum(1 for result in test_case_results if result.outcome == TestOutcome.FAIL)
    errored = sum(1 for result in test_case_results if result.outcome == TestOutcome.ERROR)
    skipped = sum(1 for result in test_case_results if result.outcome == TestOutcome.SKIP)
    total_cases = len(test_case_results)
    pass_rate = passed / total_cases if total_cases else 0.0

    critical_failures: list[str] = []
    for item in test_case_results:
        if item.outcome != TestOutcome.PASS and item.scenario_type in config.edge_case_types:
            critical_failures.append(f"SAFETY:{item.scenario_type}:{item.test_id}")
        if item.outcome != TestOutcome.PASS and "timeout" in item.actual_behavior.lower():
            critical_failures.append(f"SAFETY:TIMEOUT:{item.test_id}")

    pipeline_latency_percentiles = latency_profile.percentiles
    profit_accuracy_metrics = {
        "executed_count": float(accuracy_report.executed_count),
        "mean_error_pct": accuracy_report.mean_error_pct,
        "median_error_pct": accuracy_report.median_error_pct,
        "p95_error_pct": accuracy_report.p95_error_pct,
        "pct_within_1pct": accuracy_report.pct_within_1pct,
        "pct_within_5pct": accuracy_report.pct_within_5pct,
    }
    edge_case_summary = {result.scenario_type: result.outcome for result in edge_results}

    report = IntegrationTestReport(
        report_id=f"report-{now_ms()}",
        session_config=config,
        total_cases=total_cases,
        passed=passed,
        failed=failed,
        errored=errored,
        skipped=skipped,
        pass_rate=pass_rate,
        mainnet_deployment_approved=pass_rate >= 0.95,
        critical_failures=critical_failures,
        pipeline_latency_percentiles=pipeline_latency_percentiles,
        profit_accuracy_metrics=profit_accuracy_metrics,
        edge_case_results=edge_case_summary,
        generated_at=now_ms(),
        test_case_results=test_case_results,
        decision_accuracy=decision_accuracy,
        funnel_report=funnel_report,
        latency_profile=latency_profile,
        accuracy_report=accuracy_report,
    )

    gate = DeploymentGateValidator().evaluate(report, latency_profile=latency_profile, accuracy_report=accuracy_report)

    output_path = Path(args.output_report)
    dump_report(report, str(output_path))
    latency_path = output_path.parent / "latest_latency.md"
    latency_path.parent.mkdir(parents=True, exist_ok=True)
    latency_path.write_text(latency_markdown, encoding="utf-8")

    summary_status = "PASS" if gate.approved else "FAIL"
    deployment_status = "APPROVED" if gate.approved else "BLOCKED"
    print(
        f"INTEGRATION TEST RESULT: {summary_status} — {passed}/{total_cases} cases ({pass_rate:.1%}) — Mainnet deployment: {deployment_status}"
    )
    print(latency_markdown)
    print(gate.explanation)

    return 0 if gate.approved else 1


if __name__ == "__main__":
    raise SystemExit(main())
