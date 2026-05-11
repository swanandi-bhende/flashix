from __future__ import annotations

from decimal import Decimal
from typing import Callable

import pytest

from compute.arbitrage_analyzer import InferenceInput, analyze

from .determinism_validator import DeterminismValidator
from .inference_replay import InputValidationError, TestCase, coerce_inference_output, now_ts, validate_input_snapshot


def _make_input(
    *,
    opportunity_id: str,
    price_a: Decimal,
    price_b: Decimal,
    funding_rate_a: Decimal = Decimal("0.0001"),
    funding_rate_b: Decimal = Decimal("0.00005"),
    orderbook_depth_a: float = 50000.0,
    orderbook_depth_b: float = 50000.0,
    volatility_24h: float = 0.6,
    gas_price_gwei: float = 40.0,
    spread_momentum_5s: float = 0.01,
    timestamp: int | None = None,
) -> InferenceInput:
    return InferenceInput(
        opportunity_id=opportunity_id,
        symbol="BTC-PERP",
        dex_a="dexA",
        dex_b="dexB",
        price_a=price_a,
        price_b=price_b,
        borrow_amount_usdc=Decimal("10000"),
        funding_rate_a=funding_rate_a,
        funding_rate_b=funding_rate_b,
        orderbook_depth_a=orderbook_depth_a,
        orderbook_depth_b=orderbook_depth_b,
        trade_flow_imbalance_a=0.05,
        trade_flow_imbalance_b=-0.02,
        volatility_24h=volatility_24h,
        correlation_btc=0.25,
        timestamp=timestamp if timestamp is not None else now_ts(),
        chain_id=1337,
        gas_price_gwei=gas_price_gwei,
        spread_momentum_5s=spread_momentum_5s,
    )


def _run(input_obj: InferenceInput) -> dict:
    response = analyze(input_obj.__dict__)
    assert "result" in response
    return response["result"]


def _assert_skip(input_obj: InferenceInput) -> None:
    output = coerce_inference_output(_run(input_obj))
    assert output.decision == "SKIP"


def _assert_execute(input_obj: InferenceInput) -> None:
    output = coerce_inference_output(_run(input_obj))
    assert output.decision == "EXECUTE"


def test_flash_crash_always_produces_skip() -> None:
    cases = [
        _make_input(opportunity_id=f"flash-{idx}", price_a=Decimal(str(100 - drop)), price_b=Decimal("100"), funding_rate_a=Decimal("-0.05") - Decimal(str(idx)) * Decimal("0.01"), orderbook_depth_a=100.0 / (idx + 1), orderbook_depth_b=150.0 / (idx + 1), volatility_24h=4.5 + idx * 0.1, gas_price_gwei=120.0 + idx * 10.0, spread_momentum_5s=-0.05 * (idx + 1))
        for idx, drop in enumerate([20, 25, 30, 40, 50])
    ]
    for case in cases:
        _assert_skip(case)


def test_funding_rate_spike_makes_trade_unprofitable() -> None:
    input_obj = _make_input(
        opportunity_id="funding-spike",
        price_a=Decimal("104.0"),
        price_b=Decimal("100.0"),
        funding_rate_a=Decimal("0.009"),
        funding_rate_b=Decimal("0.0001"),
        gas_price_gwei=80.0,
    )
    output = coerce_inference_output(_run(input_obj))
    assert output.expected_profit_usdc <= 0 or output.decision == "SKIP"


def test_zero_liquidity_rejected() -> None:
    input_obj = _make_input(
        opportunity_id="zero-liquidity",
        price_a=Decimal("103.5"),
        price_b=Decimal("100.0"),
        orderbook_depth_a=100.0,
        orderbook_depth_b=75.0,
        volatility_24h=1.0,
    )
    with pytest.raises(InputValidationError, match="liquidity"):
        validate_input_snapshot(input_obj)
    output = coerce_inference_output(_run(input_obj))
    assert output.confidence < 0.5


def test_stale_timestamp_rejected_before_model() -> None:
    input_obj = _make_input(
        opportunity_id="stale-ts",
        price_a=Decimal("101.0"),
        price_b=Decimal("100.0"),
        timestamp=now_ts() - 120,
    )
    with pytest.raises(InputValidationError, match="timestamp"):
        validate_input_snapshot(input_obj)


def test_extreme_spread_flagged_as_suspicious() -> None:
    input_obj = _make_input(opportunity_id="extreme-spread", price_a=Decimal("115.0"), price_b=Decimal("100.0"), volatility_24h=1.0)
    output = coerce_inference_output(_run(input_obj))
    assert output.decision == "SKIP" or output.risk_score > 0.8


def test_borderline_confidence_consistent_across_100_runs() -> None:
    input_obj = _make_input(opportunity_id="borderline-751", price_a=Decimal("107.51"), price_b=Decimal("100.0"), volatility_24h=0.7)
    validator = DeterminismValidator()
    test_case = TestCase(
        test_id="borderline-751",
        test_name="borderline_confidence_751",
        scenario_type="BORDERLINE_CONFIDENCE",
        input=input_obj,
        expected_decision="EXECUTE",
        expected_profit_range=(Decimal("1"), Decimal("200")),
        expected_confidence_range=(0.751, 0.751),
        notes="Confidence just above the threshold should always execute.",
    )
    determinism_result = validator.validate_single(test_case, n_runs=100)
    assert determinism_result.all_identical
    outputs = [coerce_inference_output(_run(input_obj)) for _ in range(100)]
    assert all(output.decision == "EXECUTE" for output in outputs)


def _build_flash_crash_case(drop_pct: int, idx: int) -> InferenceInput:
    price_b = Decimal("100.0")
    price_a = price_b * (Decimal("1") - Decimal(str(drop_pct)) / Decimal("100"))
    return _make_input(
        opportunity_id=f"flash-{drop_pct}-{idx}",
        price_a=price_a,
        price_b=price_b,
        funding_rate_a=Decimal("-0.05") - Decimal(str(idx)) * Decimal("0.005"),
        orderbook_depth_a=50.0 / (idx + 1),
        orderbook_depth_b=70.0 / (idx + 1),
        volatility_24h=4.5 + idx * 0.1,
        gas_price_gwei=120.0 + idx * 10.0,
        spread_momentum_5s=-0.05 * (idx + 1),
    )


def _build_funding_spike_case(idx: int) -> InferenceInput:
    return _make_input(
        opportunity_id=f"funding-{idx}",
        price_a=Decimal("104.0") + Decimal(str(idx)) * Decimal("0.1"),
        price_b=Decimal("100.0"),
        funding_rate_a=Decimal("0.009"),
        funding_rate_b=Decimal("0.0001"),
        gas_price_gwei=70.0 + idx * 5.0,
    )


def _build_zero_liquidity_case(idx: int) -> InferenceInput:
    return _make_input(
        opportunity_id=f"zero-{idx}",
        price_a=Decimal("103.5") + Decimal(str(idx)) * Decimal("0.05"),
        price_b=Decimal("100.0"),
        orderbook_depth_a=100.0 + idx * 5.0,
        orderbook_depth_b=80.0 + idx * 5.0,
        volatility_24h=1.0 + idx * 0.05,
    )


def _build_extreme_spread_case(idx: int) -> InferenceInput:
    spread = Decimal("15.0") - Decimal(str(idx)) * Decimal("0.2")
    price_b = Decimal("100.0")
    price_a = price_b * (Decimal("1") + spread / Decimal("100"))
    return _make_input(opportunity_id=f"extreme-{idx}", price_a=price_a, price_b=price_b, volatility_24h=1.2)


def _build_high_volatility_case(idx: int) -> InferenceInput:
    return _make_input(
        opportunity_id=f"vol-{idx}",
        price_a=Decimal("103.0") + Decimal(str(idx)) * Decimal("0.1"),
        price_b=Decimal("100.0"),
        volatility_24h=4.5 - idx * 0.05,
        gas_price_gwei=50.0 + idx * 2.0,
    )


def _build_network_congestion_case(idx: int) -> InferenceInput:
    return _make_input(
        opportunity_id=f"congest-{idx}",
        price_a=Decimal("104.0"),
        price_b=Decimal("100.0"),
        gas_price_gwei=120.0 + idx * 15.0,
        spread_momentum_5s=0.01 * idx,
    )


def _register_generated_test(name: str, builder: Callable[[int], InferenceInput], assertion: Callable[[InferenceInput], None], idx: int) -> None:
    def _test() -> None:
        assertion(builder(idx))

    _test.__name__ = name
    globals()[name] = _test


def _build_flash_crash_variant(idx: int) -> InferenceInput:
    drop = [20, 25, 30, 40, 50][idx - 1]
    return _build_flash_crash_case(drop, idx)


for idx in range(1, 6):
    _register_generated_test(
        f"test_flash_crash_variant_{idx}",
        _build_flash_crash_variant,
        _assert_skip,
        idx,
    )

for idx in range(1, 6):
    _register_generated_test(f"test_funding_rate_spike_variant_{idx}", _build_funding_spike_case, _assert_skip, idx)

for idx in range(1, 6):
    _register_generated_test(f"test_zero_liquidity_variant_{idx}", _build_zero_liquidity_case, _assert_skip, idx)

for idx in range(1, 6):
    _register_generated_test(f"test_extreme_spread_variant_{idx}", _build_extreme_spread_case, _assert_skip, idx)

for idx in range(1, 6):
    _register_generated_test(f"test_high_volatility_variant_{idx}", _build_high_volatility_case, lambda input_obj: assert_skip_or_high_risk(input_obj), idx)

for idx in range(1, 6):
    _register_generated_test(f"test_network_congestion_variant_{idx}", _build_network_congestion_case, _assert_skip, idx)


def assert_skip_or_high_risk(input_obj: InferenceInput) -> None:
    output = coerce_inference_output(_run(input_obj))
    assert output.decision == "SKIP" or output.risk_score > 0.7


def test_high_volatility_always_triggers_risk_controls() -> None:
    for idx in range(5):
        assert_skip_or_high_risk(_build_high_volatility_case(idx))


def test_network_congestion_penalizes_execution() -> None:
    for idx in range(5):
        _assert_skip(_build_network_congestion_case(idx))
