from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from decimal import Decimal
from enum import Enum
import json
import statistics
import time
from typing import Any, Literal, Optional

MIN_PASS_RATE = 0.95
MAX_CRITICAL_FAILURES = 0
MIN_OPPORTUNITIES_TESTED = 100
MAX_AVG_PIPELINE_LATENCY_MS = 45_000
MAX_PROFIT_ESTIMATION_ERROR_PCT = 5.0
MEMPPOOL_TO_FILTER_P95_MS = 200.0
INFERENCE_EXECUTION_P95_MS = 2_000.0
AGENT_REASONING_P95_MS = 25_000.0
EXECUTION_SUBMISSION_P95_MS = 5_000.0
CONFIRMATION_WAIT_P95_MS = 15_000.0
TOTAL_PIPELINE_P95_MS = MAX_AVG_PIPELINE_LATENCY_MS

DataSource = Literal["SYNTHETIC", "HISTORICAL_REPLAY", "HYBRID"]
PipelineMode = Literal["FULL", "INFERENCE_ONLY", "AGENT_ONLY", "EXECUTION_ONLY"]


class TestOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class TestSessionConfig:
    session_id: str
    data_source: DataSource
    n_opportunities: int
    pipeline_mode: PipelineMode
    dry_run_mode: bool = True
    tee_mode: str = "simulation"
    time_acceleration_factor: float = 10.0
    random_seed: int = 42
    edge_case_injection_enabled: bool = True
    edge_case_types: list[str] = field(default_factory=list)
    max_execution_time_seconds: int = 600


@dataclass(frozen=True)
class TestCaseResult:
    test_id: str
    test_name: str
    scenario_type: str
    outcome: TestOutcome
    expected_behavior: str
    actual_behavior: str
    assertion_failures: list[str]
    execution_latency_ms: float
    notes: str


@dataclass(frozen=True)
class PricePoint:
    timestamp: int
    symbol: str
    exchange: str
    price: float
    volume: float
    ohlcv: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class FundingRatePoint:
    timestamp: int
    symbol: str
    exchange: str
    funding_rate: float


@dataclass(frozen=True)
class GasPricePoint:
    timestamp: int
    gas_price_gwei: float
    source: str = "ETHERSCAN"


@dataclass(frozen=True)
class DatasetMetadata:
    start_date: str
    end_date: str
    total_minutes: int
    symbols: list[str]
    source_apis: list[str]
    fetch_timestamp: int


@dataclass(frozen=True)
class HistoricalDataset:
    price_series: dict[str, list[PricePoint]]
    funding_rate_series: dict[str, list[FundingRatePoint]]
    gas_price_series: list[GasPricePoint]
    metadata: DatasetMetadata


@dataclass(frozen=True)
class SimulatedOpportunity:
    id: str
    symbol: str
    dex_a: str
    dex_b: str
    price_a: float
    price_b: float
    gross_spread_pct: float
    funding_rate_a: float
    funding_rate_b: float
    gas_price_gwei: float
    timestamp: int
    expected_duration_minutes: int
    historical_outcome: Literal["PROFITABLE", "REVERTED", "BLOCKED", "UNKNOWN"]
    expected_profit_usdc: float
    gap_ms: int = 0
    scenario_type: str = "NORMAL"
    edge_case_type: str = ""
    collateral_ratio: float = 1.6
    market_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CorrelationTrace:
    correlation_id: str
    stage_timeline: list[dict[str, Any]]
    final_stage: str
    final_status: str
    created_at_ms: int
    completed_at_ms: int
    notes: str = ""


@dataclass(frozen=True)
class PipelineRunResult:
    opportunity: SimulatedOpportunity
    settlement: Any
    trace: CorrelationTrace
    wall_clock_latency_ms: float
    stage: str = "SETTLEMENT_COMPLETED"
    status: str = "UNKNOWN"


@dataclass(frozen=True)
class MockExecutionEvent:
    signal_id: str
    dex_a: str
    dex_b: str
    profit_realized: float
    gas_used: int
    timestamp: int


@dataclass(frozen=True)
class MockReceipt:
    tx_hash: str
    block_number: int
    block_timestamp: int
    gas_used: int
    status: int
    revert_reason: str | None = None
    event: MockExecutionEvent | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccuracyReport:
    executed_count: int
    mean_error_pct: float
    median_error_pct: float
    p95_error_pct: float
    pct_within_1pct: float
    pct_within_5pct: float
    profit_errors: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionAccuracyReport:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class FunnelReport:
    detected: int
    passed_filter: int
    passed_inference: int
    passed_agent: int
    passed_risk: int
    executed: int
    confirmed: int
    profitable: int


@dataclass(frozen=True)
class SLAViolation:
    stage: str
    p95_ms: float
    sla_target_ms: float
    ratio: float
    affected_opportunity_pct: float


@dataclass(frozen=True)
class LatencyProfile:
    series: dict[str, list[float]]
    percentiles: dict[str, dict[str, float]]
    sla_violations: list[SLAViolation]


@dataclass(frozen=True)
class BottleneckAnalysis:
    bottleneck_stage: str
    p95_ms: float
    sla_target_ms: float
    ratio: float
    affected_opportunity_pct: float


@dataclass(frozen=True)
class DeploymentGateDecision:
    approved: bool
    explanation: str
    failing_criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IntegrationTestReport:
    report_id: str
    session_config: TestSessionConfig
    total_cases: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: float
    mainnet_deployment_approved: bool
    critical_failures: list[str]
    pipeline_latency_percentiles: dict[str, dict[str, float]]
    profit_accuracy_metrics: dict[str, float]
    edge_case_results: dict[str, TestOutcome]
    generated_at: int
    test_case_results: list[TestCaseResult] = field(default_factory=list)
    decision_accuracy: DecisionAccuracyReport | None = None
    funnel_report: FunnelReport | None = None
    latency_profile: LatencyProfile | None = None
    accuracy_report: AccuracyReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


class DeploymentGateValidator:
    def evaluate(
        self,
        report: IntegrationTestReport,
        *,
        latency_profile: LatencyProfile | None = None,
        accuracy_report: AccuracyReport | None = None,
    ) -> DeploymentGateDecision:
        failures: list[str] = []

        if report.pass_rate < MIN_PASS_RATE:
            failures.append(f"PASS_RATE_BELOW_MINIMUM ({report.pass_rate:.3f} < {MIN_PASS_RATE:.2f})")
        if len(report.critical_failures) > MAX_CRITICAL_FAILURES:
            failures.append(f"CRITICAL_FAILURES_PRESENT ({len(report.critical_failures)})")
        if report.total_cases < MIN_OPPORTUNITIES_TESTED:
            failures.append(f"INSUFFICIENT_OPPORTUNITIES_TESTED ({report.total_cases} < {MIN_OPPORTUNITIES_TESTED})")

        latency_payload = latency_profile or report.latency_profile
        if latency_payload is not None:
            if latency_payload.sla_violations:
                failures.append("LATENCY_SLA_VIOLATIONS_PRESENT")
            for stage, metrics in latency_payload.percentiles.items():
                if stage == "total_pipeline" and metrics.get("p95", 0.0) > MAX_AVG_PIPELINE_LATENCY_MS:
                    failures.append(f"TOTAL_PIPELINE_LATENCY_EXCEEDED ({metrics.get('p95', 0.0):.1f}ms)")

        accuracy_payload = accuracy_report or report.accuracy_report
        if accuracy_payload is not None and accuracy_payload.pct_within_5pct < 0.95:
            failures.append(f"PROFIT_ACCURACY_BELOW_TARGET ({accuracy_payload.pct_within_5pct:.3f})")
        elif report.profit_accuracy_metrics:
            within_5 = float(report.profit_accuracy_metrics.get("pct_within_5pct", 0.0))
            if within_5 < 0.95:
                failures.append(f"PROFIT_ACCURACY_BELOW_TARGET ({within_5:.3f})")

        approved = not failures
        explanation = "All deployment criteria satisfied." if approved else "; ".join(failures)
        return DeploymentGateDecision(approved=approved, explanation=explanation, failing_criteria=failures)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def dump_report(report: IntegrationTestReport, path: str) -> None:
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def load_report(path: str) -> IntegrationTestReport:
    payload = json.loads(open(path, "r", encoding="utf-8").read())
    return IntegrationTestReport(
        report_id=payload["report_id"],
        session_config=TestSessionConfig(**payload["session_config"]),
        total_cases=int(payload["total_cases"]),
        passed=int(payload["passed"]),
        failed=int(payload["failed"]),
        errored=int(payload["errored"]),
        skipped=int(payload["skipped"]),
        pass_rate=float(payload["pass_rate"]),
        mainnet_deployment_approved=bool(payload["mainnet_deployment_approved"]),
        critical_failures=list(payload.get("critical_failures", [])),
        pipeline_latency_percentiles=dict(payload.get("pipeline_latency_percentiles", {})),
        profit_accuracy_metrics=dict(payload.get("profit_accuracy_metrics", {})),
        edge_case_results={key: TestOutcome(value) for key, value in payload.get("edge_case_results", {}).items()},
        generated_at=int(payload["generated_at"]),
    )


def now_ms() -> int:
    return int(time.time() * 1000)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = (len(ordered) - 1) * (q / 100.0)
    lower = int(index)
    upper = min(len(ordered) - 1, lower + 1)
    weight = index - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize_numeric(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "mean": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "count": float(len(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }


__all__ = [
    "AGENT_REASONING_P95_MS",
    "AccuracyReport",
    "BottleneckAnalysis",
    "CONFIRMATION_WAIT_P95_MS",
    "CorrelationTrace",
    "DataSource",
    "DatasetMetadata",
    "DeploymentGateDecision",
    "DeploymentGateValidator",
    "EXECUTION_SUBMISSION_P95_MS",
    "FundingRatePoint",
    "FunnelReport",
    "GasPricePoint",
    "HistoricalDataset",
    "INFERENCE_EXECUTION_P95_MS",
    "IntegrationTestReport",
    "LatencyProfile",
    "MAX_AVG_PIPELINE_LATENCY_MS",
    "MAX_CRITICAL_FAILURES",
    "MAX_PROFIT_ESTIMATION_ERROR_PCT",
    "MEMPPOOL_TO_FILTER_P95_MS",
    "MIN_OPPORTUNITIES_TESTED",
    "MIN_PASS_RATE",
    "MockExecutionEvent",
    "MockReceipt",
    "PipelineMode",
    "PipelineRunResult",
    "PricePoint",
    "SLAViolation",
    "SimulatedOpportunity",
    "TESTCASE_RESULT" if False else "TestCaseResult",
    "TestCaseResult",
    "TestOutcome",
    "TestSessionConfig",
    "TOTAL_PIPELINE_P95_MS",
    "DecisionAccuracyReport",
    "dump_report",
    "load_report",
    "now_ms",
    "percentile",
    "summarize_numeric",
]
