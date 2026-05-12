from __future__ import annotations

import logging
import os
import time
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import requests

from agent.metrics import (
    ALERT_DAILY_PNL_WARN_USDC,
    ALERT_DRAWDOWN_WARN_PCT,
    ALERT_EXECUTION_SUCCESS_RATE_MIN,
    ALERT_INFERENCE_LATENCY_P95_MAX_MS,
    ALERT_OPEN_BREAKERS_CRITICAL,
    ALERT_QUEUE_DEPTH_MAX,
    Alert,
    AlertSeverity,
    Metric,
    MetricName,
)
from agent.metrics.financial_metrics import FinancialMetricsCalculator
from agent.metrics.metrics_store import MetricsStore
from agent.risk_manager import BreakerType
from agent.risk.risk_registry import RiskRegistry

logger = logging.getLogger(__name__)


def _severity_rank(severity: AlertSeverity) -> int:
    return {
        AlertSeverity.INFO: 1,
        AlertSeverity.WARNING: 2,
        AlertSeverity.CRITICAL: 3,
        AlertSeverity.EMERGENCY: 4,
    }[severity]


class AlertEngine:
    def __init__(
        self,
        risk_registry: RiskRegistry,
        metrics_store: MetricsStore | None = None,
        financial_calculator: FinancialMetricsCalculator | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.risk_registry = risk_registry
        self.metrics_store = metrics_store
        self.financial_calculator = financial_calculator or FinancialMetricsCalculator()
        self.webhook_url = webhook_url or os.getenv("ALERT_WEBHOOK_URL", "")
        self.active_alerts: dict[MetricName, Alert] = {}

    def evaluate(self, snapshot: dict[str, Metric]) -> list[Alert]:
        alerts: list[Alert] = []
        checks = [
            self._check_execution_success(snapshot),
            self._check_inference_latency(snapshot),
            self._check_drawdown(snapshot),
            self._check_queue_depth(snapshot),
            self._check_daily_pnl(snapshot),
            self._check_open_breakers(snapshot),
        ]
        for alert in checks:
            if alert is None:
                continue
            alerts.append(alert)
            if self.metrics_store is not None:
                self.metrics_store.upsert_alert(alert)
        return alerts

    def _metric_value(self, snapshot: dict[str, Metric], name: MetricName, default: float = 0.0) -> float:
        for metric in snapshot.values():
            if metric.name == name:
                return float(metric.value)
        return default

    def _record_active(self, alert: Alert) -> Alert:
        current = self.active_alerts.get(alert.metric_name)
        if current is None:
            self.active_alerts[alert.metric_name] = alert
            self.deliver_webhook(alert)
            if self.metrics_store is not None:
                self.metrics_store.upsert_alert(alert)
            return alert
        if _severity_rank(alert.severity) > _severity_rank(current.severity):
            updated = replace(current, severity=alert.severity, current_value=alert.current_value, threshold_value=alert.threshold_value, message=alert.message)
            self.active_alerts[alert.metric_name] = updated
            self.deliver_webhook(updated)
            if self.metrics_store is not None:
                self.metrics_store.upsert_alert(updated)
            return updated
        updated = replace(current, current_value=alert.current_value, threshold_value=alert.threshold_value, message=alert.message)
        self.active_alerts[alert.metric_name] = updated
        if self.metrics_store is not None:
            self.metrics_store.upsert_alert(updated)
        return updated

    def resolve_alert(self, metric_name: MetricName) -> None:
        alert = self.active_alerts.pop(metric_name, None)
        if alert is None:
            return
        resolved = replace(alert, resolved_at=int(time.time()), acknowledged=alert.acknowledged)
        if self.metrics_store is not None:
            self.metrics_store.upsert_alert(resolved)
        logger.info("ALERT_RESOLVED: %s, was=%s, now=%s", metric_name.value, alert.current_value, resolved.current_value)

    def _check_execution_success(self, snapshot: dict[str, Metric]) -> Alert | None:
        metric = next((item for item in snapshot.values() if item.name == MetricName.EXECUTION_SUCCESS_RATE), None)
        if metric is None:
            return None
        if metric.value >= ALERT_EXECUTION_SUCCESS_RATE_MIN:
            self.resolve_alert(MetricName.EXECUTION_SUCCESS_RATE)
            return None
        alert = Alert(
            alert_id=str(uuid4()),
            severity=AlertSeverity.CRITICAL,
            metric_name=MetricName.EXECUTION_SUCCESS_RATE,
            current_value=float(metric.value),
            threshold_value=ALERT_EXECUTION_SUCCESS_RATE_MIN,
            message=f"Execution success rate {metric.value:.1%} below threshold {ALERT_EXECUTION_SUCCESS_RATE_MIN:.1%} — investigate immediately",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        return self._record_active(alert)

    def _check_inference_latency(self, snapshot: dict[str, Metric]) -> Alert | None:
        metric = next((item for item in snapshot.values() if item.name == MetricName.INFERENCE_LATENCY_P95_MS), None)
        if metric is None:
            return None
        if metric.value <= ALERT_INFERENCE_LATENCY_P95_MAX_MS:
            self.resolve_alert(MetricName.INFERENCE_LATENCY_P95_MS)
            return None
        severity = AlertSeverity.WARNING if metric.value > 1500 else AlertSeverity.CRITICAL
        if metric.value > ALERT_INFERENCE_LATENCY_P95_MAX_MS:
            severity = AlertSeverity.CRITICAL
        alert = Alert(
            alert_id=str(uuid4()),
            severity=severity,
            metric_name=MetricName.INFERENCE_LATENCY_P95_MS,
            current_value=float(metric.value),
            threshold_value=3000.0,
            message=f"Inference p95 latency {metric.value:.0f}ms above acceptable threshold",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        return self._record_active(alert)

    def _check_drawdown(self, snapshot: dict[str, Metric]) -> Alert | None:
        metric = next((item for item in snapshot.values() if item.name == MetricName.DRAWDOWN_FROM_PEAK_PCT), None)
        if metric is None:
            return None
        if metric.value < ALERT_DRAWDOWN_WARN_PCT:
            self.resolve_alert(MetricName.DRAWDOWN_FROM_PEAK_PCT)
            return None
        drawdown = self.financial_calculator.calculate_drawdown()
        severity = AlertSeverity.WARNING if metric.value < 30.0 else AlertSeverity.EMERGENCY
        absolute_drawdown = max(0.0, drawdown.peak_pnl_usdc - drawdown.current_pnl_usdc)
        alert = Alert(
            alert_id=str(uuid4()),
            severity=severity,
            metric_name=MetricName.DRAWDOWN_FROM_PEAK_PCT,
            current_value=float(metric.value),
            threshold_value=ALERT_DRAWDOWN_WARN_PCT if severity == AlertSeverity.WARNING else 30.0,
            message=f"Drawdown {metric.value:.1f}% ({absolute_drawdown:.2f} USDC) from peak profit requires review",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        return self._record_active(alert)

    def _check_queue_depth(self, snapshot: dict[str, Metric]) -> Alert | None:
        value = self._metric_value(snapshot, MetricName.REDIS_QUEUE_DEPTH_MAX)
        if value <= ALERT_QUEUE_DEPTH_MAX:
            return None
        alert = Alert(
            alert_id=str(uuid4()),
            severity=AlertSeverity.WARNING,
            metric_name=MetricName.REDIS_QUEUE_DEPTH_MAX,
            current_value=value,
            threshold_value=ALERT_QUEUE_DEPTH_MAX,
            message=f"Queue depth {value:.0f} exceeds threshold {ALERT_QUEUE_DEPTH_MAX:.0f}",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        return self._record_active(alert)

    def _check_daily_pnl(self, snapshot: dict[str, Metric]) -> Alert | None:
        value = self._metric_value(snapshot, MetricName.DAILY_PNL_USDC)
        if value >= float(ALERT_DAILY_PNL_WARN_USDC):
            return None
        alert = Alert(
            alert_id=str(uuid4()),
            severity=AlertSeverity.WARNING,
            metric_name=MetricName.DAILY_PNL_USDC,
            current_value=value,
            threshold_value=float(ALERT_DAILY_PNL_WARN_USDC),
            message=f"Daily P&L {value:.2f} USDC below warning threshold {ALERT_DAILY_PNL_WARN_USDC}",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        return self._record_active(alert)

    def _check_open_breakers(self, snapshot: dict[str, Metric]) -> Alert | None:
        value = self._metric_value(snapshot, MetricName.OPEN_CIRCUIT_BREAKERS_COUNT)
        if value < ALERT_OPEN_BREAKERS_CRITICAL:
            return None
        severity = AlertSeverity.CRITICAL if value < ALERT_OPEN_BREAKERS_CRITICAL + 1 else AlertSeverity.EMERGENCY
        alert = Alert(
            alert_id=str(uuid4()),
            severity=severity,
            metric_name=MetricName.OPEN_CIRCUIT_BREAKERS_COUNT,
            current_value=value,
            threshold_value=ALERT_OPEN_BREAKERS_CRITICAL,
            message=f"{value:.0f} circuit breakers are open; trading should be reviewed immediately",
            triggered_at=int(time.time()),
            resolved_at=None,
            acknowledged=False,
        )
        if severity == AlertSeverity.EMERGENCY:
            try:
                self.risk_registry.open_breaker(
                    BreakerType.HUMAN_OVERRIDE,
                    float(value),
                    opportunity_id=None,
                    auto_reset_seconds=None,
                    notes="Emergency monitoring alert",
                )
            except Exception:
                logger.exception("FAILED_TO_OPEN_HUMAN_OVERRIDE_BREAKER")
        return self._record_active(alert)

    def deliver_webhook(self, alert: Alert) -> None:
        if not self.webhook_url:
            return
        payload = {
            "alert_id": alert.alert_id,
            "severity": alert.severity.value,
            "metric_name": alert.metric_name.value,
            "current_value": alert.current_value,
            "threshold": alert.threshold_value,
            "message": alert.message,
            "triggered_at_iso": datetime.fromtimestamp(alert.triggered_at, tz=timezone.utc).isoformat(),
            "system": "Flashix",
            "environment": os.getenv("FLASHIX_ENVIRONMENT", "testnet"),
        }
        try:
            requests.post(self.webhook_url, json=payload, timeout=0.5)
        except Exception:
            logger.exception("ALERT_WEBHOOK_DELIVERY_FAILED")
