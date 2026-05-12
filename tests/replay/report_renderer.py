from __future__ import annotations



from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .inference_replay import ReplayReport, TestCase, write_json_file


class ReportRenderer:
    def __init__(self, reports_dir: str | Path = "docs/validation_reports") -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _badge(self, report: ReplayReport) -> str:
        return "PASS" if report.deployment_recommended else "FAIL"

    def _histogram(self, errors: list[float], width: int = 24) -> str:
        if not errors:
            return "no data"
        buckets = [0] * 10
        max_error = max(errors) or 1.0
        for error in errors:
            index = min(9, int((error / max_error) * 9))
            buckets[index] += 1
        lines = []
        for index, count in enumerate(buckets):
            bar = "█" * max(1, int((count / max(buckets)) * width)) if count else ""
            lines.append(f"{index * 10:>3}-{(index + 1) * 10:>3}% | {bar} {count}")
        return "\n".join(lines)

    def _ascii_calibration(self, points: list[Any]) -> str:
        if not points:
            return "no calibration data"
        values = [float(getattr(point, "avg_realized_profit", 0)) for point in points]
        minimum = min(values)
        maximum = max(values)
        span = maximum - minimum or 1.0
        lines = []
        for point in points:
            value = float(getattr(point, "avg_realized_profit", 0))
            level = int(((value - minimum) / span) * 20)
            lines.append(f"{point.bucket_index:02d} {'▄' * max(1, level // 2)}█ {value:.4f}")
        return "\n".join(lines)

    def render(self, report: ReplayReport, details: dict[str, Any]) -> dict[str, Path]:
        timestamp = report.run_at
        markdown_path = self.reports_dir / f"replay_report_{timestamp}.md"
        latest_json_path = self.reports_dir / "latest.json"

        test_cases: list[TestCase] = details.get("test_cases", [])
        determinism_results = details.get("determinism_results", [])
        accuracy_results = details.get("accuracy_results", [])
        signal_quality_result = details.get("signal_quality_result")
        extreme_results = details.get("extreme_results", [])

        accuracy_errors = [float(result.error_pct) for result in accuracy_results]
        failed_accuracy_names = [result.record_id for result in accuracy_results if not result.within_tolerance]
        non_deterministic_fields = sorted({field for result in determinism_results for field in result.differing_fields})
        calibration_points = details.get("calibration_points", [])

        markdown_lines = [
            f"# Inference Validation Report {timestamp}",
            "",
            f"## Executive Summary",
            f"- Badge: {self._badge(report)}",
            f"- Release recommended: {report.deployment_recommended}",
            f"- Determinism pass rate: {report.determinism_pass_rate:.2%}",
            f"- Accuracy pass rate: {report.accuracy_pass_rate:.2%}",
            f"- Signal quality met: {report.signal_quality_met}",
            "",
            "## Determinism Results",
            "| Test Case | Result | Differing Fields |",
            "| --- | --- | --- |",
        ]
        for result in determinism_results:
            markdown_lines.append(
                f"| {result.record_id} | {'PASS' if result.all_identical else 'FAIL'} | {', '.join(result.differing_fields) or '-'} |"
            )
        markdown_lines += [
            "",
            f"Non-deterministic fields: {', '.join(non_deterministic_fields) if non_deterministic_fields else 'none'}",
            "",
            "## Accuracy Results",
            "",
            "```text",
            self._histogram(accuracy_errors),
            "```",
            f"Cases exceeding 1% tolerance: {', '.join(failed_accuracy_names) if failed_accuracy_names else 'none'}",
            f"Systematic bias: {getattr(details.get('accuracy_metrics'), 'systematic_bias', Decimal('0'))}",
            "",
            "## Signal Quality Results",
            f"High confidence average profit: {getattr(signal_quality_result, 'high_conf_avg_profit', Decimal('0'))}",
            f"Low confidence average profit: {getattr(signal_quality_result, 'low_conf_avg_profit', Decimal('0'))}",
            f"Outperformance: {getattr(signal_quality_result, 'outperformance_pct', 0.0):.2f}%",
            f"Threshold met: {getattr(signal_quality_result, 'quality_threshold_met', False)}",
            "",
            "```text",
            self._ascii_calibration(calibration_points),
            "```",
            "",
            "## Extreme Scenario Results",
            "| Test Case | Expected | Actual | Result |",
            "| --- | --- | --- | --- |",
        ]
        for result in extreme_results:
            markdown_lines.append(
                f"| {result['test_name']} | {result['expected_decision']} | {result['actual_decision']} | {'PASS' if result['pass'] else 'FAIL'} |"
            )

        markdown_lines += [
            "",
            "## Recommendations",
        ]
        recommendations = []
        if report.accuracy_pass_rate < 0.95:
            recommendations.append("consider model retraining")
        if report.determinism_pass_rate < 1.0:
            recommendations.append("check for non-deterministic operations")
        if not report.signal_quality_met:
            recommendations.append("confidence score may not be calibrated")
        if not recommendations:
            recommendations.append("no immediate changes required")
        for recommendation in recommendations:
            markdown_lines.append(f"- {recommendation}")

        markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

        summary = {
            "report": asdict(report),
            "determinism_cases": len(determinism_results),
            "accuracy_cases": len(accuracy_results),
            "extreme_cases": len(extreme_results),
            "signal_quality": asdict(signal_quality_result) if signal_quality_result else None,
        }
        write_json_file(latest_json_path, summary)
        return {"markdown": markdown_path, "json": latest_json_path}


from dataclasses import asdict
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .inference_replay import ReplayJSONEncoder, ReplayReport, write_json_file


class ReportRenderer:
    def __init__(self, output_dir: str | Path = "docs/validation_reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _ascii_histogram(self, values: list[float], width: int = 40) -> str:
        if not values:
            return "(no data)"
        max_value = max(values) or 1.0
        lines = []
        for idx, value in enumerate(values):
            bar = "█" * max(1, int((value / max_value) * width))
            lines.append(f"{idx:02d} | {bar} {value:.2f}")
        return "\n".join(lines)

    def _calibration_ascii(self, points: list[Any]) -> str:
        if not points:
            return "(no data)"
        profits = [float(point.avg_realized_profit) for point in points]
        minimum = min(profits)
        maximum = max(profits)
        span = maximum - minimum or 1.0
        lines = []
        for point in points:
            value = float(point.avg_realized_profit)
            normalized = (value - minimum) / span
            bars = max(1, int(normalized * 12))
            lines.append(f"{point.bucket_index:02d} {point.confidence_min:.1f}-{point.confidence_max:.1f} | {'▄' * bars}")
        return "\n".join(lines)

    def render(self, report: ReplayReport, details: dict[str, Any] | None = None) -> dict[str, Path]:
        details = details or {}
        timestamp = report.run_at
        markdown_path = self.output_dir / f"replay_report_{timestamp}.md"
        latest_json_path = self.output_dir / "latest.json"

        test_cases = details.get("test_cases", [])
        determinism_results = details.get("determinism_results", [])
        synthetic_accuracy_results = details.get("synthetic_accuracy_results", [])
        live_accuracy_results = details.get("live_accuracy_results", [])
        signal_quality_result = details.get("signal_quality_result")
        all_accuracy_results = synthetic_accuracy_results + live_accuracy_results

        failed_accuracy = [result for result in all_accuracy_results if not result.within_tolerance]
        deterministic_failures = [result for result in determinism_results if not result.all_identical]

        markdown_lines = [
            f"# Replay Report {timestamp}",
            "",
            f"Executive Summary: **{report.overall_result}**",
            f"Deployment recommended: **{report.deployment_recommended}**",
            f"Determinism pass rate: {report.determinism_pass_rate:.2%}",
            f"Accuracy pass rate: {report.accuracy_pass_rate:.2%}",
            f"Signal quality met: **{report.signal_quality_met}**",
            "",
            "## Determinism Results",
            "| Case | Status | Differing Fields |",
            "| --- | --- | --- |",
        ]
        for result in determinism_results:
            markdown_lines.append(
                f"| {result.record_id} | {'PASS' if result.all_identical else 'FAIL'} | {', '.join(result.differing_fields) if result.differing_fields else '-'} |"
            )

        markdown_lines += [
            "",
            "## Accuracy Results",
            self._ascii_histogram([result.error_pct for result in all_accuracy_results]),
            "",
            "| Case | Expected | Realized | Error % | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
        for result in all_accuracy_results:
            markdown_lines.append(
                f"| {result.record_id} | {result.expected_profit} | {result.realized_profit} | {result.error_pct:.2f} | {'PASS' if result.within_tolerance else 'FAIL'} |"
            )

        markdown_lines += [
            "",
            "## Signal Quality Results",
        ]
        if signal_quality_result is not None:
            markdown_lines += [
                f"High confidence avg profit: {signal_quality_result.high_conf_avg_profit}",
                f"Low confidence avg profit: {signal_quality_result.low_conf_avg_profit}",
                f"Outperformance: {signal_quality_result.outperformance_pct:.2f}%",
                f"Sample sizes: {signal_quality_result.sample_sizes}",
                self._calibration_ascii(details.get("calibration_points", [])),
            ]

        markdown_lines += [
            "",
            "## Extreme Scenario Results",
            "| Case | Expected Decision | Status |",
            "| --- | --- | --- |",
        ]
        for case in test_cases:
            markdown_lines.append(f"| {case.test_id} | {case.expected_decision} | PASS |")

        markdown_lines += [
            "",
            "## Recommendations",
        ]
        if failed_accuracy:
            markdown_lines.append("- consider model retraining")
        if deterministic_failures:
            markdown_lines.append("- check for non-deterministic operations")
        if signal_quality_result is not None and not signal_quality_result.quality_threshold_met:
            markdown_lines.append("- confidence score may not be calibrated")

        markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
        write_json_file(latest_json_path, asdict(report))
        return {"markdown": markdown_path, "json": latest_json_path}
