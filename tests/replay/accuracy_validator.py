from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import importlib
import json
import logging
import sqlite3
from statistics import mean, median
from pathlib import Path
from typing import Any

from .inference_replay import AccuracyMetrics, AccuracyResult, InsufficientDataError, TestCase, coerce_inference_output


_logger = logging.getLogger(__name__)


class AccuracyValidator:
    def __init__(self, db_path: str | Path = "data/inference_replay.db") -> None:
        self.db_path = Path(db_path)
        self._analyzer = importlib.import_module("compute.arbitrage_analyzer")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def validate_accuracy(self, min_records: int = 30) -> list[AccuracyResult]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM inference_records
                WHERE ground_truth_status IS NOT NULL
                  AND ground_truth_status != 'NEVER_EXECUTED'
                ORDER BY recorded_at ASC
                """
            ).fetchall()

        if len(rows) < min_records:
            raise InsufficientDataError(len(rows), min_records)

        results: list[AccuracyResult] = []
        for row in rows:
            output = coerce_inference_output(json.loads(row["output_json"]))
            expected_profit = Decimal(str(output.expected_profit_usdc))
            realized_profit = Decimal(str(row["ground_truth_profit_usdc"]))
            if expected_profit == 0:
                error_pct = 0.0 if realized_profit == 0 else 100.0
            else:
                error_pct = float((abs(expected_profit - realized_profit) / abs(expected_profit)) * Decimal("100"))
            results.append(
                AccuracyResult(
                    record_id=str(row["record_id"]),
                    expected_profit=expected_profit,
                    realized_profit=realized_profit,
                    error_pct=error_pct,
                    within_tolerance=error_pct <= 1.0,
                )
            )
        return results

    def compute_accuracy_metrics(self, results: list[AccuracyResult]) -> AccuracyMetrics:
        if not results:
            return AccuracyMetrics(
                pass_rate=0.0,
                mean_error_pct=0.0,
                median_error_pct=0.0,
                p95_error_pct=0.0,
                max_error_pct=0.0,
                systematic_bias=Decimal("0"),
            )

        errors = [result.error_pct for result in results]
        pass_rate = sum(result.within_tolerance for result in results) / len(results)
        sorted_errors = sorted(errors)
        p95_index = min(len(sorted_errors) - 1, int(round((len(sorted_errors) - 1) * 0.95)))
        expected_minus_realized = [result.expected_profit - result.realized_profit for result in results]
        return AccuracyMetrics(
            pass_rate=pass_rate,
            mean_error_pct=float(mean(errors)),
            median_error_pct=float(median(errors)),
            p95_error_pct=float(sorted_errors[p95_index]),
            max_error_pct=float(max(errors)),
            systematic_bias=sum(expected_minus_realized, Decimal("0")) / Decimal(str(len(results))),
        )

    def validate_with_synthetic_ground_truth(self, test_cases: list[TestCase]) -> list[AccuracyResult]:
        results: list[AccuracyResult] = []
        for test_case in test_cases:
            if test_case.expected_profit_range is None:
                continue
            response = self._analyzer.analyze(test_case.input.__dict__)
            output = response["result"] if isinstance(response, dict) and "result" in response else response
            output = coerce_inference_output(output)
            expected_min, expected_max = test_case.expected_profit_range
            midpoint = (expected_min + expected_max) / Decimal("2")
            realized = Decimal(str(output.expected_profit_usdc))
            within_range = expected_min <= realized <= expected_max
            if midpoint == 0:
                error_pct = 0.0 if realized == 0 else 100.0
            else:
                error_pct = float((abs(midpoint - realized) / abs(midpoint)) * Decimal("100"))
            results.append(
                AccuracyResult(
                    record_id=test_case.test_id,
                    expected_profit=midpoint,
                    realized_profit=realized,
                    error_pct=error_pct,
                    within_tolerance=within_range,
                )
            )
        return results
