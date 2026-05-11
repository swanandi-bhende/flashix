from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Literal, Optional

from compute.arbitrage_analyzer import InferenceInput, InferenceOutput


ScenarioType = Literal[
    "NORMAL_PROFITABLE",
    "NORMAL_UNPROFITABLE",
    "FLASH_CRASH",
    "FUNDING_RATE_SPIKE",
    "ZERO_LIQUIDITY",
    "GAS_SPIKE",
    "HIGH_VOLATILITY",
    "SPREAD_REVERSION",
    "BORDERLINE_CONFIDENCE",
    "EXTREME_SPREAD",
    "STALE_PRICE",
    "NETWORK_CONGESTION",
]

DecisionType = Literal["EXECUTE", "SKIP", "EITHER"]
GroundTruthStatus = Literal["PROFITABLE", "UNPROFITABLE", "NEVER_EXECUTED"]
OverallResult = Literal["PASS", "FAIL", "WARN"]


@dataclass(frozen=True)
class MarketConditions:
    gas_price_gwei: float
    orderbook_depth_a: float
    orderbook_depth_b: float
    funding_rate_a: Decimal
    funding_rate_b: Decimal
    volatility_24h: float
    gross_spread_percent: float
    vix_equivalent_score: float
    liquidity_score: float
    network_congestion_score: float
    timestamp: int
    oracle_age_seconds: int
    slippage_estimate_usdc: Decimal


@dataclass(frozen=True)
class InferenceRecord:
    record_id: str
    correlation_id: str
    input_snapshot: InferenceInput
    output_snapshot: InferenceOutput
    market_state_snapshot: MarketConditions
    model_version: str
    model_checksum: str
    tee_mode: str
    inference_latency_ms: float
    recorded_at: int
    ground_truth_profit_usdc: Optional[Decimal]
    ground_truth_status: Optional[GroundTruthStatus]


@dataclass(frozen=True)
class TestCase:
    test_id: str
    test_name: str
    scenario_type: ScenarioType
    input: InferenceInput
    expected_decision: DecisionType
    expected_profit_range: Optional[tuple[Decimal, Decimal]]
    expected_confidence_range: Optional[tuple[float, float]]
    notes: str


@dataclass(frozen=True)
class DeterminismResult:
    record_id: str
    n_runs: int
    all_identical: bool
    differing_fields: list[str]
    hash_values: list[str]


@dataclass(frozen=True)
class AccuracyResult:
    record_id: str
    expected_profit: Decimal
    realized_profit: Decimal
    error_pct: float
    within_tolerance: bool


@dataclass(frozen=True)
class SignalQualityResult:
    high_conf_avg_profit: Decimal
    low_conf_avg_profit: Decimal
    outperformance_pct: float
    sample_sizes: dict[str, int]
    quality_threshold_met: bool
    win_rate_high: float = 0.0
    win_rate_low: float = 0.0


@dataclass(frozen=True)
class AccuracyMetrics:
    pass_rate: float
    mean_error_pct: float
    median_error_pct: float
    p95_error_pct: float
    max_error_pct: float
    systematic_bias: Decimal


@dataclass(frozen=True)
class CalibrationPoint:
    bucket_index: int
    confidence_min: float
    confidence_max: float
    avg_realized_profit: Decimal
    sample_size: int


@dataclass(frozen=True)
class ReplayReport:
    report_id: str
    run_at: int
    model_version: str
    total_test_cases: int
    determinism_pass_rate: float
    accuracy_pass_rate: float
    signal_quality_met: bool
    failed_cases: list[str]
    critical_failures: list[str]
    overall_result: OverallResult
    deployment_recommended: bool


def coerce_market_conditions(payload: dict[str, Any] | MarketConditions) -> MarketConditions:
    if isinstance(payload, MarketConditions):
        return payload
    return MarketConditions(
        gas_price_gwei=float(payload["gas_price_gwei"]),
        orderbook_depth_a=float(payload["orderbook_depth_a"]),
        orderbook_depth_b=float(payload["orderbook_depth_b"]),
        funding_rate_a=_coerce_decimal(payload["funding_rate_a"]),
        funding_rate_b=_coerce_decimal(payload["funding_rate_b"]),
        volatility_24h=float(payload["volatility_24h"]),
        gross_spread_percent=float(payload["gross_spread_percent"]),
        vix_equivalent_score=float(payload["vix_equivalent_score"]),
        liquidity_score=float(payload["liquidity_score"]),
        network_congestion_score=float(payload["network_congestion_score"]),
        timestamp=int(payload["timestamp"]),
        oracle_age_seconds=int(payload["oracle_age_seconds"]),
        slippage_estimate_usdc=_coerce_decimal(payload["slippage_estimate_usdc"]),
    )


class InsufficientDataError(RuntimeError):
    def __init__(self, actual_count: int, min_records: int) -> None:
        self.actual_count = actual_count
        self.min_records = min_records
        super().__init__(f"Insufficient data: actual_count={actual_count}, min_records={min_records}")


class InputValidationError(ValueError):
    pass


class ReplayJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


def json_dumps(data: Any, *, sort_keys: bool = True, indent: int | None = None) -> str:
    return json.dumps(data, cls=ReplayJSONEncoder, sort_keys=sort_keys, indent=indent)


def stable_hash(data: Any) -> str:
    return sha256(json_dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def _coerce_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def coerce_inference_input(payload: dict[str, Any] | InferenceInput) -> InferenceInput:
    if isinstance(payload, InferenceInput):
        return payload
    return InferenceInput(
        opportunity_id=str(payload["opportunity_id"]),
        symbol=str(payload["symbol"]),
        dex_a=str(payload["dex_a"]),
        dex_b=str(payload["dex_b"]),
        price_a=_coerce_decimal(payload["price_a"]),
        price_b=_coerce_decimal(payload["price_b"]),
        borrow_amount_usdc=_coerce_decimal(payload["borrow_amount_usdc"]),
        funding_rate_a=_coerce_decimal(payload["funding_rate_a"]),
        funding_rate_b=_coerce_decimal(payload["funding_rate_b"]),
        orderbook_depth_a=float(payload["orderbook_depth_a"]),
        orderbook_depth_b=float(payload["orderbook_depth_b"]),
        trade_flow_imbalance_a=float(payload["trade_flow_imbalance_a"]),
        trade_flow_imbalance_b=float(payload["trade_flow_imbalance_b"]),
        volatility_24h=float(payload["volatility_24h"]),
        correlation_btc=float(payload["correlation_btc"]),
        timestamp=int(payload["timestamp"]),
        chain_id=int(payload["chain_id"]),
        gas_price_gwei=float(payload["gas_price_gwei"]),
        spread_momentum_5s=float(payload["spread_momentum_5s"]),
    )


def coerce_inference_output(payload: dict[str, Any] | InferenceOutput) -> InferenceOutput:
    if isinstance(payload, InferenceOutput):
        return payload
    return InferenceOutput(
        opportunity_id=str(payload["opportunity_id"]),
        primary_dex=str(payload["primary_dex"]),
        counter_dex=str(payload["counter_dex"]),
        borrow_amount=_coerce_decimal(payload["borrow_amount"]),
        collateral_required=_coerce_decimal(payload["collateral_required"]),
        expected_profit_usdc=_coerce_decimal(payload.get("expected_profit_usdc", payload.get("expected_profit", 0))),
        risk_score=float(payload["risk_score"]),
        confidence=float(payload["confidence"]),
        decision=str(payload["decision"]),
        expiry_timestamp=int(payload["expiry_timestamp"]),
        reasoning=str(payload.get("reasoning", "")),
        model_version=str(payload.get("model_version", "unknown")),
        input_hash=str(payload.get("input_hash", "")),
        output_hash=str(payload.get("output_hash", "")),
        tee_signature=str(payload.get("tee_signature", "")),
    )


def serialize_dataclass(obj: Any) -> dict[str, Any]:
    if not is_dataclass(obj):
        raise TypeError(f"Expected dataclass instance, got {type(obj)!r}")
    return asdict(obj)


def ensure_parent(path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def now_ts() -> int:
    return int(time.time())


def write_json_file(path: str | Path, payload: Any) -> Path:
    resolved = ensure_parent(path)
    resolved.write_text(json_dumps(payload, indent=2), encoding="utf-8")
    return resolved


def read_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_input_snapshot(input_snapshot: InferenceInput, *, max_age_seconds: int = 30) -> None:
    age_seconds = now_ts() - int(input_snapshot.timestamp)
    if age_seconds > max_age_seconds:
        raise InputValidationError(f"timestamp too old: age_seconds={age_seconds}")
    if float(input_snapshot.orderbook_depth_a) < 1000 or float(input_snapshot.orderbook_depth_b) < 1000:
        raise InputValidationError("orderbook depth below minimum liquidity threshold")
    gross_spread_percent = abs(float(input_snapshot.price_a) - float(input_snapshot.price_b)) / min(
        float(input_snapshot.price_a),
        float(input_snapshot.price_b),
    ) * 100.0
    if gross_spread_percent > 15.0:
        raise InputValidationError("gross spread exceeds suspicious range")
