from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
import itertools
import json
from typing import Iterable

from compute.arbitrage_analyzer import InferenceInput

from .inference_replay import ReplayJSONEncoder, TestCase, coerce_inference_input, json_dumps, now_ts, write_json_file


class TestCaseGenerator:
    def __init__(self, fixture_path: str | Path = "tests/fixtures/test_cases.json") -> None:
        self.fixture_path = Path(fixture_path)

    def _base_input(
        self,
        *,
        opportunity_id: str,
        symbol: str = "BTC-PERP",
        price_a: Decimal = Decimal("100.0"),
        price_b: Decimal = Decimal("97.0"),
        borrow_amount_usdc: Decimal = Decimal("10000"),
        funding_rate_a: Decimal = Decimal("0.0001"),
        funding_rate_b: Decimal = Decimal("0.00005"),
        orderbook_depth_a: float = 50000.0,
        orderbook_depth_b: float = 50000.0,
        trade_flow_imbalance_a: float = 0.05,
        trade_flow_imbalance_b: float = -0.02,
        volatility_24h: float = 0.6,
        correlation_btc: float = 0.25,
        timestamp: int | None = None,
        chain_id: int = 1337,
        gas_price_gwei: float = 40.0,
        spread_momentum_5s: float = 0.01,
    ) -> InferenceInput:
        return InferenceInput(
            opportunity_id=opportunity_id,
            symbol=symbol,
            dex_a="dexA",
            dex_b="dexB",
            price_a=price_a,
            price_b=price_b,
            borrow_amount_usdc=borrow_amount_usdc,
            funding_rate_a=funding_rate_a,
            funding_rate_b=funding_rate_b,
            orderbook_depth_a=orderbook_depth_a,
            orderbook_depth_b=orderbook_depth_b,
            trade_flow_imbalance_a=trade_flow_imbalance_a,
            trade_flow_imbalance_b=trade_flow_imbalance_b,
            volatility_24h=volatility_24h,
            correlation_btc=correlation_btc,
            timestamp=timestamp if timestamp is not None else now_ts(),
            chain_id=chain_id,
            gas_price_gwei=gas_price_gwei,
            spread_momentum_5s=spread_momentum_5s,
        )

    def _make_case(
        self,
        *,
        prefix: str,
        index: int,
        scenario_type: str,
        test_name: str,
        input_obj: InferenceInput,
        expected_decision: str,
        expected_profit_range: tuple[Decimal, Decimal] | None,
        expected_confidence_range: tuple[float, float] | None,
        notes: str,
    ) -> TestCase:
        return TestCase(
            test_id=f"{prefix}-{index:03d}",
            test_name=test_name,
            scenario_type=scenario_type,  # type: ignore[arg-type]
            input=input_obj,
            expected_decision=expected_decision,  # type: ignore[arg-type]
            expected_profit_range=expected_profit_range,
            expected_confidence_range=expected_confidence_range,
            notes=notes,
        )

    def _generate_normal_profitable(self, n: int = 15) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            spread = Decimal("3.5") + (Decimal(idx) * Decimal("0.15"))
            price_b = Decimal("100.0")
            price_a = price_b * (Decimal("1") + spread / Decimal("100"))
            cases.append(
                self._make_case(
                    prefix="normal-profit",
                    index=idx,
                    scenario_type="NORMAL_PROFITABLE",
                    test_name=f"normal_profitable_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"np-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        funding_rate_a=Decimal("0.0001"),
                        funding_rate_b=Decimal("0.00005"),
                        volatility_24h=0.5 + (idx % 3) * 0.05,
                        gas_price_gwei=35.0 + idx,
                    ),
                    expected_decision="EXECUTE",
                    expected_profit_range=(Decimal("50"), Decimal("500")),
                    expected_confidence_range=(0.80, 0.95),
                    notes="Stable profitable spread with healthy liquidity.",
                )
            )
        return cases

    def _generate_normal_unprofitable(self, n: int = 10) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            spread = Decimal("0.6") + (Decimal(idx) * Decimal("0.08"))
            price_b = Decimal("100.0")
            price_a = price_b * (Decimal("1") + spread / Decimal("100"))
            cases.append(
                self._make_case(
                    prefix="normal-loss",
                    index=idx,
                    scenario_type="NORMAL_UNPROFITABLE",
                    test_name=f"normal_unprofitable_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"nu-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        borrow_amount_usdc=Decimal("5000"),
                        gas_price_gwei=60.0 + idx,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-200"), Decimal("100")),
                    expected_confidence_range=(0.0, 0.74),
                    notes="Spread is below costs after fees and slippage.",
                )
            )
        return cases

    def _generate_flash_crash(self, n: int = 10) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            drop_pct = Decimal("15") + (Decimal(idx) * Decimal("1.2"))
            price_b = Decimal("100.0")
            price_a = price_b * (Decimal("1") - drop_pct / Decimal("100"))
            cases.append(
                self._make_case(
                    prefix="flash-crash",
                    index=idx,
                    scenario_type="FLASH_CRASH",
                    test_name=f"flash_crash_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"fc-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        funding_rate_a=Decimal("-0.05") - Decimal(idx) * Decimal("0.004"),
                        funding_rate_b=Decimal("0.00002"),
                        orderbook_depth_a=50.0 + idx,
                        orderbook_depth_b=75.0 + idx,
                        volatility_24h=4.5 + (idx % 5) * 0.1,
                        gas_price_gwei=120.0 + idx * 2,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-500"), Decimal("100")),
                    expected_confidence_range=(0.0, 0.65),
                    notes="Flash crash signature with near-zero depth and extreme negative funding.",
                )
            )
        return cases

    def _generate_funding_rate_spike(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            spread = Decimal("4.0") + Decimal(idx) * Decimal("0.2")
            price_b = Decimal("100.0")
            price_a = price_b * (Decimal("1") + spread / Decimal("100"))
            cases.append(
                self._make_case(
                    prefix="funding-spike",
                    index=idx,
                    scenario_type="FUNDING_RATE_SPIKE",
                    test_name=f"funding_rate_spike_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"fr-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        funding_rate_a=Decimal("0.010") + Decimal(idx) * Decimal("0.001"),
                        funding_rate_b=Decimal("0.0001"),
                        gas_price_gwei=80.0 + idx,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-80"), Decimal("15")),
                    expected_confidence_range=(0.0, 0.74),
                    notes="Borrow cost pressure should erase the spread edge.",
                )
            )
        return cases

    def _generate_zero_liquidity(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            price_b = Decimal("100.0")
            price_a = Decimal("103.5")
            cases.append(
                self._make_case(
                    prefix="zero-liquidity",
                    index=idx,
                    scenario_type="ZERO_LIQUIDITY",
                    test_name=f"zero_liquidity_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"zl-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        orderbook_depth_a=100.0 + idx * 10.0,
                        orderbook_depth_b=75.0 + idx * 8.0,
                        volatility_24h=1.2,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-500"), Decimal("100")),
                    expected_confidence_range=(0.0, 0.55),
                    notes="Liquidity is too thin to safely size the trade.",
                )
            )
        return cases

    def _generate_borderline_confidence(self, n: int = 15) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            conf = 0.749 if idx % 2 == 0 else 0.751
            price_b = Decimal("100.0")
            price_a = Decimal("104.0") if conf > 0.75 else Decimal("103.0")
            cases.append(
                self._make_case(
                    prefix="borderline-confidence",
                    index=idx,
                    scenario_type="BORDERLINE_CONFIDENCE",
                    test_name=f"borderline_confidence_{idx}_{conf}",
                    input_obj=self._base_input(
                        opportunity_id=f"bc-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        volatility_24h=0.7,
                        gas_price_gwei=45.0,
                    ),
                    expected_decision="EXECUTE" if conf > 0.75 else "SKIP",
                    expected_profit_range=(Decimal("5"), Decimal("120")),
                    expected_confidence_range=(conf - 0.001, conf + 0.001),
                    notes="Boundary case around the decision threshold.",
                )
            )
        return cases

    def _generate_extreme_spread(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            spread = Decimal("10.5") + Decimal(idx) * Decimal("0.5")
            price_b = Decimal("100.0")
            price_a = price_b * (Decimal("1") + spread / Decimal("100"))
            cases.append(
                self._make_case(
                    prefix="extreme-spread",
                    index=idx,
                    scenario_type="EXTREME_SPREAD",
                    test_name=f"extreme_spread_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"es-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        volatility_24h=1.0,
                        gas_price_gwei=55.0 + idx,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-100"), Decimal("200")),
                    expected_confidence_range=(0.0, 0.9),
                    notes="Unrealistically large spread should be treated as suspicious data.",
                )
            )
        return cases

    def _generate_stale_price(self, n: int = 5) -> list[TestCase]:
        cases: list[TestCase] = []
        stale_ts = now_ts() - 90
        for idx in range(n):
            cases.append(
                self._make_case(
                    prefix="stale-price",
                    index=idx,
                    scenario_type="STALE_PRICE",
                    test_name=f"stale_price_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"sp-{idx}",
                        price_a=Decimal("101.0"),
                        price_b=Decimal("100.0"),
                        timestamp=stale_ts,
                        gas_price_gwei=35.0,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=None,
                    expected_confidence_range=None,
                    notes="Timestamp is stale and should be rejected by freshness validation.",
                )
            )
        return cases

    def _generate_spread_reversion(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            price_b = Decimal("100.0")
            price_a = Decimal("102.0") + Decimal(idx) * Decimal("0.3")
            cases.append(
                self._make_case(
                    prefix="spread-reversion",
                    index=idx,
                    scenario_type="SPREAD_REVERSION",
                    test_name=f"spread_reversion_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"sr-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        spread_momentum_5s=-0.02 - idx * 0.002,
                        volatility_24h=0.8,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("80"), Decimal("350")),
                    expected_confidence_range=(0.2, 0.8),
                    notes="Price action is already reverting by the time the signal is formed.",
                )
            )
        return cases

    def _generate_gas_spike(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            price_b = Decimal("100.0")
            price_a = Decimal("104.0")
            cases.append(
                self._make_case(
                    prefix="gas-spike",
                    index=idx,
                    scenario_type="GAS_SPIKE",
                    test_name=f"gas_spike_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"gs-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        gas_price_gwei=250.0 + idx * 10.0,
                        volatility_24h=0.9,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("50"), Decimal("300")),
                    expected_confidence_range=(0.0, 0.8),
                    notes="Gas spike should dominate net profit and suppress execution.",
                )
            )
        return cases

    def _generate_high_volatility(self, n: int = 8) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            price_b = Decimal("100.0")
            price_a = Decimal("103.0") + Decimal(idx) * Decimal("0.1")
            cases.append(
                self._make_case(
                    prefix="high-volatility",
                    index=idx,
                    scenario_type="HIGH_VOLATILITY",
                    test_name=f"high_volatility_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"hv-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        volatility_24h=4.7 - idx * 0.02,
                        gas_price_gwei=70.0,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("50"), Decimal("300")),
                    expected_confidence_range=(0.0, 0.75),
                    notes="Volatility is near the top of the risk envelope.",
                )
            )
        return cases

    def _generate_network_congestion(self, n: int = 7) -> list[TestCase]:
        cases: list[TestCase] = []
        for idx in range(n):
            price_b = Decimal("100.0")
            price_a = Decimal("104.5")
            cases.append(
                self._make_case(
                    prefix="network-congestion",
                    index=idx,
                    scenario_type="NETWORK_CONGESTION",
                    test_name=f"network_congestion_{idx}",
                    input_obj=self._base_input(
                        opportunity_id=f"nc-{idx}",
                        price_a=price_a,
                        price_b=price_b,
                        gas_price_gwei=90.0 + idx * 15.0,
                        volatility_24h=1.1,
                        spread_momentum_5s=0.005 * idx,
                    ),
                    expected_decision="SKIP",
                    expected_profit_range=(Decimal("-60"), Decimal("30")),
                    expected_confidence_range=(0.0, 0.8),
                    notes="Congestion should delay fills and inflate execution risk.",
                )
            )
        return cases

    def generate_all(self) -> list[TestCase]:
        cases = []
        cases.extend(self._generate_normal_profitable())
        cases.extend(self._generate_normal_unprofitable())
        cases.extend(self._generate_flash_crash())
        cases.extend(self._generate_funding_rate_spike())
        cases.extend(self._generate_zero_liquidity())
        cases.extend(self._generate_borderline_confidence())
        cases.extend(self._generate_extreme_spread())
        cases.extend(self._generate_stale_price())
        cases.extend(self._generate_spread_reversion())
        cases.extend(self._generate_gas_spike())
        cases.extend(self._generate_high_volatility())
        cases.extend(self._generate_network_congestion())
        self.save_fixture(cases)
        return cases

    def save_fixture(self, cases: Iterable[TestCase]) -> Path:
        payload = [asdict(case) for case in cases]
        return write_json_file(self.fixture_path, payload)

    def load_fixture(self) -> list[TestCase]:
        raw_cases = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        parsed: list[TestCase] = []
        for item in raw_cases:
            parsed.append(
                TestCase(
                    test_id=item["test_id"],
                    test_name=item["test_name"],
                    scenario_type=item["scenario_type"],
                    input=coerce_inference_input(item["input"]),
                    expected_decision=item["expected_decision"],
                    expected_profit_range=
                    tuple(Decimal(str(x)) for x in item["expected_profit_range"]) if item.get("expected_profit_range") else None,
                    expected_confidence_range=
                    tuple(float(x) for x in item["expected_confidence_range"]) if item.get("expected_confidence_range") else None,
                    notes=item.get("notes", ""),
                )
            )
        return parsed
