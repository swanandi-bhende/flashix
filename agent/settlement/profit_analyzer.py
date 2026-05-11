from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from statistics import mean, median
from typing import Any

from agent.settlement_monitor import BiasReport, HighVarianceCondition, ProfitVarianceAnalysis, SettlementRecord


class ProfitVarianceAnalyzer:
    def __init__(self, ledger: Any) -> None:
        self.ledger = ledger

    def analyze(self, expected: Decimal, realized: Decimal, settlement: SettlementRecord) -> ProfitVarianceAnalysis:
        variance_usdc = realized - expected
        if expected == 0:
            variance_pct = 0.0 if realized == 0 else 100.0
        else:
            variance_pct = float((variance_usdc / expected) * Decimal("100"))

        if abs(variance_pct) <= 1.0:
            direction = "ACCURATE"
        elif variance_usdc < 0:
            direction = "OVERESTIMATED"
        else:
            direction = "UNDERESTIMATED"

        expected_gas_cost = Decimal(str(getattr(settlement, "gas_cost_usdc", Decimal("0")) or Decimal("0")))
        gas_cost = Decimal(str(getattr(settlement, "gas_cost_usdc", Decimal("0")) or Decimal("0")))
        if gas_cost > expected_gas_cost * Decimal("1.3"):
            driver = "GAS_UNDERSTIMATION"
        elif realized < expected * Decimal("0.97") and gas_cost <= expected_gas_cost * Decimal("1.3"):
            driver = "SLIPPAGE_UNDERSTIMATION"
        elif realized > expected * Decimal("1.03"):
            driver = "COST_OVERESTIMATION"
        else:
            driver = "MIXED"

        return ProfitVarianceAnalysis(
            expected_usdc=expected,
            realized_usdc=realized,
            variance_usdc=variance_usdc,
            variance_pct=variance_pct,
            variance_direction=direction,
            primary_variance_driver=driver,
        )

    def compute_rolling_bias(self, lookback_n: int = 50) -> BiasReport:
        records = self.ledger.list_records(limit=lookback_n)
        variances = [float(record.profit_variance_pct) for record in records if record.profit_variance_pct is not None]
        if not variances:
            return BiasReport(0.0, 0.0, 0, "INSUFFICIENT_DATA", "collect more settlement outcomes")

        mean_variance_pct = float(mean(variances))
        median_variance_pct = float(median(variances))
        if mean_variance_pct < -2.0:
            return BiasReport(mean_variance_pct, median_variance_pct, len(variances), "SYSTEMATIC_OVERESTIMATION", "tighten MIN_PROFIT_MARGIN")
        if mean_variance_pct > 2.0:
            return BiasReport(mean_variance_pct, median_variance_pct, len(variances), "SYSTEMATIC_UNDERESTIMATION", "consider a more aggressive execution threshold")
        return BiasReport(mean_variance_pct, median_variance_pct, len(variances), "BALANCED", "keep current calibration")

    def identify_high_variance_conditions(self, lookback_n: int = 100) -> list[HighVarianceCondition]:
        records = self.ledger.list_records(limit=lookback_n)
        bins: dict[str, list[float]] = defaultdict(list)
        for record in records:
            if record.profit_variance_pct is None:
                continue
            vix_score = float(getattr(record, "market_vix_score", 0.0) or 0.0)
            if vix_score < 33:
                vix_bin = "low_vix"
            elif vix_score < 66:
                vix_bin = "medium_vix"
            else:
                vix_bin = "high_vix"

            settled_hour = int(record.settled_at // 1000 // 3600 % 24)
            if settled_hour < 8:
                time_bin = "morning_utc"
            elif settled_hour < 16:
                time_bin = "afternoon_utc"
            else:
                time_bin = "evening_utc"

            position_size = Decimal(str(getattr(record, "position_size_usdc", record.expected_profit_usdc)))
            if position_size < Decimal("10"):
                size_bin = "small_position"
            elif position_size < Decimal("50"):
                size_bin = "medium_position"
            else:
                size_bin = "large_position"

            bins[f"{vix_bin} | {time_bin} | {size_bin}"].append(float(record.profit_variance_pct))

        result: list[HighVarianceCondition] = []
        for description, values in bins.items():
            avg = float(mean(values))
            if abs(avg) > 3.0:
                result.append(
                    HighVarianceCondition(
                        condition_description=description,
                        mean_variance_pct=avg,
                        sample_count=len(values),
                        recommended_action="tighten slippage and profit buffers for this market regime",
                    )
                )
        return sorted(result, key=lambda item: abs(item.mean_variance_pct), reverse=True)
