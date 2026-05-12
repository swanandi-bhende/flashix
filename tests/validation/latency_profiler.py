from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

from tests.integration_test import (
    AGENT_REASONING_P95_MS,
    CONFIRMATION_WAIT_P95_MS,
    EXECUTION_SUBMISSION_P95_MS,
    INFERENCE_EXECUTION_P95_MS,
    LatencyProfile,
    MEMPPOOL_TO_FILTER_P95_MS,
    PipelineRunResult,
    SLAViolation,
    TOTAL_PIPELINE_P95_MS,
    BottleneckAnalysis,
    percentile,
)


class LatencyProfiler:
    SLA_TARGETS = {
        "mempool_to_filter": MEMPPOOL_TO_FILTER_P95_MS,
        "inference_execution": INFERENCE_EXECUTION_P95_MS,
        "agent_reasoning": AGENT_REASONING_P95_MS,
        "execution_submission": EXECUTION_SUBMISSION_P95_MS,
        "confirmation_wait": CONFIRMATION_WAIT_P95_MS,
        "total_pipeline": TOTAL_PIPELINE_P95_MS,
    }

    def profile(self, results: list[PipelineRunResult]) -> LatencyProfile:
        series: dict[str, list[float]] = {stage: [] for stage in self.SLA_TARGETS}
        for result in results:
            for item in getattr(result.trace, "stage_timeline", []):
                stage = str(item.get("stage", "")).lower()
                entered = item.get("entered_at_ms")
                exited = item.get("exited_at_ms")
                if stage in series and entered is not None and exited is not None:
                    series[stage].append(max(0.0, float(exited) - float(entered)))

        percentiles: dict[str, dict[str, float]] = {}
        sla_violations: list[SLAViolation] = []
        for stage, values in series.items():
            if np is not None and values:
                p50, p75, p90, p95, p99 = [float(value) for value in np.percentile(values, [50, 75, 90, 95, 99])]
            else:
                p50 = percentile(values, 50)
                p75 = percentile(values, 75)
                p90 = percentile(values, 90)
                p95 = percentile(values, 95)
                p99 = percentile(values, 99)
            percentiles[stage] = {"p50": p50, "p75": p75, "p90": p90, "p95": p95, "p99": p99}
            sla_target = self.SLA_TARGETS[stage]
            if p95 > sla_target:
                sla_violations.append(
                    SLAViolation(
                        stage=stage,
                        p95_ms=p95,
                        sla_target_ms=sla_target,
                        ratio=(p95 / sla_target) if sla_target else float("inf"),
                        affected_opportunity_pct=(len(values) / len(results) * 100.0) if results else 0.0,
                    )
                )

        return LatencyProfile(series=series, percentiles=percentiles, sla_violations=sla_violations)

    def identify_bottleneck(self, profile: LatencyProfile) -> BottleneckAnalysis:
        worst_stage = ""
        worst_ratio = -1.0
        for stage, metrics in profile.percentiles.items():
            target = self.SLA_TARGETS.get(stage, 1.0)
            ratio = metrics.get("p95", 0.0) / target if target else float("inf")
            if ratio > worst_ratio:
                worst_ratio = ratio
                worst_stage = stage
        stage_values = profile.series.get(worst_stage, [])
        affected_pct = 0.0
        if stage_values:
            affected_pct = len(stage_values) / max(1, max(len(values) for values in profile.series.values() or [[1]])) * 100.0
        metrics = profile.percentiles.get(worst_stage, {})
        return BottleneckAnalysis(
            bottleneck_stage=worst_stage,
            p95_ms=float(metrics.get("p95", 0.0)),
            sla_target_ms=float(self.SLA_TARGETS.get(worst_stage, 0.0)),
            ratio=float(worst_ratio),
            affected_opportunity_pct=float(affected_pct),
        )

    def generate_latency_report_markdown(self, profile: LatencyProfile) -> str:
        rows = ["| Stage | p50 (ms) | p95 (ms) | p99 (ms) | SLA Target (ms) | Status |", "| --- | ---: | ---: | ---: | ---: | --- |"]
        for stage, metrics in profile.percentiles.items():
            target = self.SLA_TARGETS.get(stage, 0.0)
            status = "PASS" if metrics.get("p95", 0.0) <= target else "FAIL"
            rows.append(
                f"| {stage} | {metrics.get('p50', 0.0):.1f} | {metrics.get('p95', 0.0):.1f} | {metrics.get('p99', 0.0):.1f} | {target:.1f} | {status} |"
            )
        return "\n".join(rows)
