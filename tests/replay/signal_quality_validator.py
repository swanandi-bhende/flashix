from __future__ import annotations

from decimal import Decimal
import importlib
import json
import logging
import sqlite3
from statistics import mean
from pathlib import Path
from typing import Any

from .inference_replay import CalibrationPoint, InsufficientDataError, SignalQualityResult, TestCase, coerce_inference_output


_logger = logging.getLogger(__name__)


class SignalQualityValidator:
    def __init__(self, db_path: str | Path = "data/inference_replay.db") -> None:
        self.db_path = Path(db_path)
        self._analyzer = importlib.import_module("compute.arbitrage_analyzer")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _aggregate(self, rows: list[sqlite3.Row], confidence_threshold: float) -> SignalQualityResult:
        high_conf = []
        low_conf = []
        for row in rows:
            output = coerce_inference_output(json.loads(row["output_json"]))
            profit = Decimal(str(row["ground_truth_profit_usdc"]))
            if float(output.confidence) >= confidence_threshold:
                high_conf.append(profit)
            else:
                low_conf.append(profit)

        if len(high_conf) < 10 or len(low_conf) < 10:
            raise InsufficientDataError(min(len(high_conf), len(low_conf)), 10)

        high_avg = Decimal(str(mean(high_conf)))
        low_avg = Decimal(str(mean(low_conf)))
        if low_avg == 0:
            outperformance_pct = float("inf") if high_avg > 0 else 0.0
        else:
            outperformance_pct = float(((high_avg - low_avg) / abs(low_avg)) * Decimal("100"))

        return SignalQualityResult(
            high_conf_avg_profit=high_avg,
            low_conf_avg_profit=low_avg,
            outperformance_pct=outperformance_pct,
            sample_sizes={"high_confidence": len(high_conf), "low_confidence": len(low_conf)},
            quality_threshold_met=outperformance_pct >= 2.0,
            win_rate_high=sum(1 for profit in high_conf if profit > 0) / len(high_conf),
            win_rate_low=sum(1 for profit in low_conf if profit > 0) / len(low_conf),
        )

    def validate_signal_quality(self, confidence_threshold: float = 0.85) -> SignalQualityResult:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM inference_records
                WHERE ground_truth_status IS NOT NULL
                  AND ground_truth_status != 'NEVER_EXECUTED'
                ORDER BY recorded_at ASC
                """
            ).fetchall()
        return self._aggregate(rows, confidence_threshold)

    def validate_with_synthetic_data(self, test_cases: list[TestCase], confidence_threshold: float = 0.85) -> SignalQualityResult:
        high_conf = []
        low_conf = []
        for test_case in test_cases:
            if test_case.expected_profit_range is None or test_case.expected_confidence_range is None:
                continue
            midpoint_conf = sum(test_case.expected_confidence_range) / 2.0
            midpoint_profit = sum(test_case.expected_profit_range) / Decimal("2")
            if midpoint_conf >= confidence_threshold:
                high_conf.append(midpoint_profit)
            else:
                low_conf.append(midpoint_profit)

        if len(high_conf) < 10 or len(low_conf) < 10:
            raise InsufficientDataError(min(len(high_conf), len(low_conf)), 10)

        high_avg = Decimal(str(mean(high_conf)))
        low_avg = Decimal(str(mean(low_conf)))
        if low_avg == 0:
            outperformance_pct = float("inf") if high_avg > 0 else 0.0
        else:
            outperformance_pct = float(((high_avg - low_avg) / abs(low_avg)) * Decimal("100"))

        return SignalQualityResult(
            high_conf_avg_profit=high_avg,
            low_conf_avg_profit=low_avg,
            outperformance_pct=outperformance_pct,
            sample_sizes={"high_confidence": len(high_conf), "low_confidence": len(low_conf)},
            quality_threshold_met=outperformance_pct >= 2.0,
            win_rate_high=sum(1 for profit in high_conf if profit > 0) / len(high_conf),
            win_rate_low=sum(1 for profit in low_conf if profit > 0) / len(low_conf),
        )

    def compute_calibration_curve(self, n_buckets: int = 10) -> list[CalibrationPoint]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT output_json, ground_truth_profit_usdc FROM inference_records
                    WHERE ground_truth_status IS NOT NULL
                      AND ground_truth_status != 'NEVER_EXECUTED'
                    """
                ).fetchall()
        except Exception:
            rows = []

        buckets: dict[int, list[Decimal]] = {idx: [] for idx in range(n_buckets)}
        for row in rows:
            try:
                output = coerce_inference_output(json.loads(row["output_json"]))
                confidence = max(0.0, min(0.999999, float(output.confidence)))
                bucket_index = min(n_buckets - 1, int(confidence * n_buckets))
                buckets[bucket_index].append(Decimal(str(row["ground_truth_profit_usdc"])))
            except Exception:
                continue

        points: list[CalibrationPoint] = []
        for bucket_index in range(n_buckets):
            lower = bucket_index / n_buckets
            upper = (bucket_index + 1) / n_buckets
            profits = buckets[bucket_index]
            points.append(
                CalibrationPoint(
                    bucket_index=bucket_index,
                    confidence_min=lower,
                    confidence_max=upper,
                    avg_realized_profit=Decimal(str(mean(profits))) if profits else Decimal("0"),
                    sample_size=len(profits),
                )
            )
        return points
