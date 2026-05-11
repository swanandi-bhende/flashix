from __future__ import annotations



from dataclasses import asdict
from decimal import Decimal
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

from .accuracy_validator import AccuracyValidator
from .determinism_validator import DeterminismValidator
from .inference_replay import (
    AccuracyResult,
    AccuracyMetrics,
    DeterminismResult,
    ReplayReport,
    SignalQualityResult,
    TestCase,
    coerce_inference_output,
    now_ts,
    read_json_file,
    write_json_file,
)
from .report_renderer import ReportRenderer
from .signal_quality_validator import SignalQualityValidator
from .test_case_generator import TestCaseGenerator


_logger = logging.getLogger(__name__)


class ReplayHarness:
    def __init__(
        self,
        fixture_path: str | Path = "tests/fixtures/test_cases.json",
        db_path: str | Path = "data/inference_replay.db",
        reports_dir: str | Path = "docs/validation_reports",
    ) -> None:
        self.fixture_path = Path(fixture_path)
        self.db_path = Path(db_path)
        self.reports_dir = Path(reports_dir)
        self.generator = TestCaseGenerator(self.fixture_path)
        self.determinism_validator = DeterminismValidator()
        self.accuracy_validator = AccuracyValidator(self.db_path)
        self.signal_quality_validator = SignalQualityValidator(self.db_path)
        self.renderer = ReportRenderer(self.reports_dir)

    def _ensure_test_cases(self) -> list[TestCase]:
        if self.fixture_path.exists():
            return self.generator.load_fixture()
        return self.generator.generate_all()

    def _live_record_count(self) -> int:
        if not self.db_path.exists():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM inference_records
                WHERE ground_truth_status IS NOT NULL
                  AND ground_truth_status != 'NEVER_EXECUTED'
                """
            ).fetchone()
        return int(row[0]) if row else 0

    def _evaluate_extreme_cases(self, test_cases: list[TestCase]) -> list[dict[str, Any]]:
        import importlib

        analyzer = importlib.import_module("compute.arbitrage_analyzer")
        extreme_results: list[dict[str, Any]] = []
        for test_case in test_cases:
            if test_case.scenario_type not in {
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
            }:
                continue
            response = analyzer.analyze(test_case.input.__dict__)
            output = response["result"] if isinstance(response, dict) and "result" in response else response
            output = coerce_inference_output(output)
            extreme_results.append(
                {
                    "test_id": test_case.test_id,
                    "test_name": test_case.test_name,
                    "scenario_type": test_case.scenario_type,
                    "expected_decision": test_case.expected_decision,
                    "actual_decision": output.decision,
                    "pass": test_case.expected_decision in {"EITHER", output.decision},
                    "confidence": float(output.confidence),
                    "expected_confidence_range": test_case.expected_confidence_range,
                }
            )
        return extreme_results

    def run_full_validation(self, include_live_records: bool = True) -> ReplayReport:
        started_at = time.time()
        phase_started = time.time()
        _logger.info("PHASE 1 START: load")
        test_cases = self._ensure_test_cases()
        live_record_count = self._live_record_count() if include_live_records else 0
        _logger.info(
            "PHASE 1 END: load in %.2fs (test_cases=%s, live_records=%s)",
            time.time() - phase_started,
            len(test_cases),
            live_record_count,
        )

        phase_started = time.time()
        _logger.info("PHASE 2 START: determinism")
        determinism_results = self.determinism_validator.validate_batch(test_cases, n_runs=10)
        determinism_pass_rate = (
            sum(1 for result in determinism_results if result.all_identical) / len(determinism_results)
            if determinism_results
            else 0.0
        )
        _logger.info("PHASE 2 END: determinism in %.2fs", time.time() - phase_started)

        phase_started = time.time()
        _logger.info("PHASE 3 START: accuracy")
        synthetic_accuracy_results = self.accuracy_validator.validate_with_synthetic_ground_truth(test_cases)
        live_accuracy_results: list[AccuracyResult] = []
        if include_live_records and live_record_count >= 30:
            try:
                live_accuracy_results = self.accuracy_validator.validate_accuracy(min_records=30)
            except Exception as exc:
                _logger.warning("Live accuracy validation skipped: %s", exc)
        accuracy_results = synthetic_accuracy_results + live_accuracy_results
        accuracy_metrics = self.accuracy_validator.compute_accuracy_metrics(accuracy_results)
        accuracy_pass_rate = (
            sum(1 for result in accuracy_results if result.within_tolerance) / len(accuracy_results)
            if accuracy_results
            else 0.0
        )
        _logger.info("PHASE 3 END: accuracy in %.2fs", time.time() - phase_started)

        phase_started = time.time()
        _logger.info("PHASE 4 START: signal_quality")
        synthetic_signal_quality = self.signal_quality_validator.validate_with_synthetic_data(test_cases)
        signal_quality_result: SignalQualityResult = synthetic_signal_quality
        if include_live_records and live_record_count >= 20:
            try:
                signal_quality_result = self.signal_quality_validator.validate_signal_quality()
            except Exception as exc:
                _logger.warning("Live signal quality validation skipped: %s", exc)
        calibration_points = self.signal_quality_validator.compute_calibration_curve()
        _logger.info("PHASE 4 END: signal_quality in %.2fs", time.time() - phase_started)

        phase_started = time.time()
        _logger.info("PHASE 5 START: report_generation")
        extreme_results = self._evaluate_extreme_cases(test_cases)
        failed_cases = [
            result.record_id for result in determinism_results if not result.all_identical
        ] + [
            result.record_id for result in accuracy_results if not result.within_tolerance
        ] + [
            result["test_id"] for result in extreme_results if not result["pass"]
        ]
        critical_failures = []
        if determinism_pass_rate < 1.0:
            critical_failures.append("DETERMINISM_FAILURE")
        if accuracy_pass_rate < 0.95:
            critical_failures.append("ACCURACY_FAILURE")
        if not signal_quality_result.quality_threshold_met:
            critical_failures.append("SIGNAL_QUALITY_FAILURE")

        overall_result = (
            "PASS"
            if determinism_pass_rate == 1.0 and accuracy_pass_rate >= 0.95 and signal_quality_result.quality_threshold_met
            else "FAIL"
        )
        report = ReplayReport(
            report_id=f"replay-{now_ts()}",
            run_at=now_ts(),
            model_version="v1",
            total_test_cases=len(test_cases),
            determinism_pass_rate=determinism_pass_rate,
            accuracy_pass_rate=accuracy_pass_rate,
            signal_quality_met=signal_quality_result.quality_threshold_met,
            failed_cases=sorted(set(failed_cases)),
            critical_failures=critical_failures,
            overall_result=overall_result,
            deployment_recommended=overall_result == "PASS",
        )

        self.renderer.render(
            report,
            {
                "test_cases": test_cases,
                "determinism_results": determinism_results,
                "accuracy_results": accuracy_results,
                "accuracy_metrics": accuracy_metrics,
                "signal_quality_result": signal_quality_result,
                "calibration_points": calibration_points,
                "extreme_results": extreme_results,
            },
        )

        elapsed_seconds = time.time() - started_at
        if elapsed_seconds > 300:
            _logger.warning("VALIDATION_SLOW: %.2fs", elapsed_seconds)
        _logger.info("PHASE 5 END: report_generation in %.2fs", time.time() - phase_started)
        return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the Flashix inference replay harness")
    parser.add_argument("--ci-mode", action="store_true", help="Exit non-zero when deployment is not recommended")
    parser.add_argument("--no-live-records", action="store_true", help="Skip live database validations")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    report = ReplayHarness().run_full_validation(include_live_records=not args.no_live_records)
    print(json.dumps(asdict(report), indent=2, default=str))
    if args.ci_mode and not report.deployment_recommended:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


from dataclasses import asdict
import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

from .accuracy_validator import AccuracyValidator
from .determinism_validator import DeterminismValidator
from .inference_replay import ReplayJSONEncoder, ReplayReport, TestCase, now_ts, stable_hash
from .report_renderer import ReportRenderer
from .signal_quality_validator import SignalQualityValidator
from .test_case_generator import TestCaseGenerator


_logger = logging.getLogger(__name__)


class ReplayHarness:
    def __init__(self, fixture_path: str | Path = "tests/fixtures/test_cases.json", db_path: str | Path = "data/inference_replay.db") -> None:
        self.fixture_path = Path(fixture_path)
        self.db_path = Path(db_path)
        self.generator = TestCaseGenerator(self.fixture_path)
        self.determinism_validator = DeterminismValidator()
        self.accuracy_validator = AccuracyValidator(self.db_path)
        self.signal_quality_validator = SignalQualityValidator(self.db_path)
        self.renderer = ReportRenderer()

    def _load_test_cases(self) -> list[TestCase]:
        if self.fixture_path.exists():
            return self.generator.load_fixture()
        return self.generator.generate_all()

    def _live_record_count(self) -> int:
        if not self.db_path.exists():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM inference_records WHERE ground_truth_status IS NOT NULL AND ground_truth_status != 'NEVER_EXECUTED'"
            ).fetchone()
            return int(row[0]) if row else 0

    def run_full_validation(self, include_live_records: bool = True) -> ReplayReport:
        start_time = time.perf_counter()
        report_id = stable_hash({"fixture_path": str(self.fixture_path), "run_at": now_ts()})[:16]
        test_cases = []
        determinism_results = []
        synthetic_accuracy_results = []
        live_accuracy_results = []
        synthetic_signal_quality = None
        live_signal_quality = None

        phase_start = time.perf_counter()
        _logger.info("PHASE_START: load")
        test_cases = self._load_test_cases()
        live_record_count = self._live_record_count() if include_live_records else 0
        _logger.info(
            "PHASE_END: load duration_ms=%s cases=%s live_records=%s",
            round((time.perf_counter() - phase_start) * 1000, 2),
            len(test_cases),
            live_record_count,
        )

        phase_start = time.perf_counter()
        _logger.info("PHASE_START: determinism")
        determinism_results = self.determinism_validator.validate_batch(test_cases, n_runs=10)
        determinism_pass_rate = sum(result.all_identical for result in determinism_results) / max(1, len(determinism_results))
        _logger.info(
            "PHASE_END: determinism duration_ms=%s pass_rate=%s",
            round((time.perf_counter() - phase_start) * 1000, 2),
            determinism_pass_rate,
        )

        phase_start = time.perf_counter()
        _logger.info("PHASE_START: accuracy")
        synthetic_accuracy_results = self.accuracy_validator.validate_with_synthetic_ground_truth(test_cases)
        if include_live_records and live_record_count > 0:
            try:
                live_accuracy_results = self.accuracy_validator.validate_accuracy()
            except Exception as exc:
                _logger.warning("Live accuracy validation skipped: %s", exc)
        combined_accuracy_results = synthetic_accuracy_results + live_accuracy_results
        accuracy_pass_rate = (
            sum(result.within_tolerance for result in combined_accuracy_results) / len(combined_accuracy_results)
            if combined_accuracy_results
            else 0.0
        )
        _logger.info(
            "PHASE_END: accuracy duration_ms=%s pass_rate=%s",
            round((time.perf_counter() - phase_start) * 1000, 2),
            accuracy_pass_rate,
        )

        phase_start = time.perf_counter()
        _logger.info("PHASE_START: signal_quality")
        synthetic_signal_quality = self.signal_quality_validator.validate_with_synthetic_data(test_cases)
        if include_live_records and live_record_count >= 20:
            try:
                live_signal_quality = self.signal_quality_validator.validate_signal_quality()
            except Exception as exc:
                _logger.warning("Live signal quality validation skipped: %s", exc)
        signal_quality_result = live_signal_quality or synthetic_signal_quality
        _logger.info(
            "PHASE_END: signal_quality duration_ms=%s met=%s",
            round((time.perf_counter() - phase_start) * 1000, 2),
            signal_quality_result.quality_threshold_met,
        )

        failed_cases = [result.record_id for result in determinism_results if not result.all_identical]
        failed_cases.extend(result.record_id for result in synthetic_accuracy_results if not result.within_tolerance)
        if live_accuracy_results:
            failed_cases.extend(result.record_id for result in live_accuracy_results if not result.within_tolerance)

        critical_failures = []
        if determinism_pass_rate < 1.0:
            critical_failures.append("NON_DETERMINISTIC_OUTPUTS")
        if accuracy_pass_rate < 0.95:
            critical_failures.append("ACCURACY_BELOW_THRESHOLD")
        if not signal_quality_result.quality_threshold_met:
            critical_failures.append("SIGNAL_QUALITY_BELOW_THRESHOLD")

        overall_result = "PASS" if not critical_failures else "FAIL"
        deployment_recommended = overall_result == "PASS"

        report = ReplayReport(
            report_id=report_id,
            run_at=now_ts(),
            model_version=str(getattr(test_cases[0].input, "opportunity_id", "unknown")) if test_cases else "unknown",
            total_test_cases=len(test_cases),
            determinism_pass_rate=determinism_pass_rate,
            accuracy_pass_rate=accuracy_pass_rate,
            signal_quality_met=signal_quality_result.quality_threshold_met,
            failed_cases=failed_cases,
            critical_failures=critical_failures,
            overall_result=overall_result,  # type: ignore[arg-type]
            deployment_recommended=deployment_recommended,
        )

        self.renderer.render(report, {
            "test_cases": test_cases,
            "determinism_results": determinism_results,
            "synthetic_accuracy_results": synthetic_accuracy_results,
            "live_accuracy_results": live_accuracy_results,
            "signal_quality_result": signal_quality_result,
        })

        total_duration = time.perf_counter() - start_time
        if total_duration > 300:
            _logger.warning("VALIDATION_SLOW duration_s=%s", round(total_duration, 2))
        else:
            _logger.info("VALIDATION_COMPLETE duration_s=%s", round(total_duration, 2))

        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Flashix inference replay validation suite")
    parser.add_argument("--ci-mode", action="store_true", help="Print the final ReplayReport JSON and exit non-zero on failure")
    parser.add_argument("--include-live-records", action="store_true", default=True)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    harness = ReplayHarness()
    report = harness.run_full_validation(include_live_records=args.include_live_records)
    report_json = json.dumps(asdict(report), cls=ReplayJSONEncoder, sort_keys=True, indent=2)
    if args.ci_mode:
        print(report_json)
        return 0 if report.deployment_recommended else 1
    print(report_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
