from __future__ import annotations

import logging
import os
import threading
import time
from decimal import Decimal
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query

from agent.market_data.freshness_monitor import FreshnessMonitor
from agent.market_data.window_store import MarketStateWindowStore
from agent.metrics import METRICS_API_PORT, MetricName
from agent.metrics.alert_engine import AlertEngine
from agent.metrics.bottleneck_profiler import BottleneckProfiler
from agent.metrics.collector import MetricsCollector
from agent.metrics.inference_recorder import InferenceRecorder
from agent.metrics.financial_metrics import FinancialMetricsCalculator
from agent.metrics.metrics_store import MetricsStore
from agent.pipeline.queue_manager import QueueManager
from agent.risk.position_watchdog import PositionWatchdog
from agent.risk.risk_registry import RiskRegistry
from agent.settlement.ledger import SettlementLedger

logger = logging.getLogger(__name__)


def _build_default_components() -> dict[str, Any]:
    ledger = SettlementLedger()
    registry = RiskRegistry()
    window_store = MarketStateWindowStore(tracked_symbols=["BTC-USD-PERP", "ETH-USD-PERP"])
    queue_manager = QueueManager()
    inference_recorder = InferenceRecorder()
    position_watchdog = PositionWatchdog(registry=registry, auto_start=False)
    freshness_monitor = FreshnessMonitor()
    metrics_store = MetricsStore()
    collector = MetricsCollector(
        settlement_ledger=ledger,
        risk_registry=registry,
        window_store=window_store,
        queue_manager=queue_manager,
        inference_recorder=inference_recorder,
        position_watchdog=position_watchdog,
        freshness_monitor=freshness_monitor,
        metrics_store=metrics_store,
        auto_start=False,
    )
    profiler = BottleneckProfiler(redis_client=queue_manager._client, sqlite_path="data/trades.db", auto_start=False)
    alert_engine = AlertEngine(risk_registry=registry, metrics_store=metrics_store, financial_calculator=FinancialMetricsCalculator(ledger.db_path))
    return {
        "ledger": ledger,
        "registry": registry,
        "window_store": window_store,
        "queue_manager": queue_manager,
        "inference_recorder": inference_recorder,
        "position_watchdog": position_watchdog,
        "freshness_monitor": freshness_monitor,
        "metrics_store": metrics_store,
        "collector": collector,
        "profiler": profiler,
        "alert_engine": alert_engine,
        "financial": FinancialMetricsCalculator(ledger.db_path),
    }


_COMPONENTS = _build_default_components()
_COMPONENTS["collector"].start_background_collection()

app = FastAPI(title="Flashix Metrics Dashboard API", version="1.0.0")


def _snapshot_to_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    latest_by_name: dict[str, Any] = {}
    for key, metric in snapshot.items():
        current = latest_by_name.get(metric.name.value)
        if current is not None and current.timestamp_ms > metric.timestamp_ms:
            continue
        latest_by_name[metric.name.value] = metric
    for name, metric in latest_by_name.items():
        payload[name] = {
            "name": metric.name.value,
            "type": metric.type.value,
            "value": metric.value,
            "labels": metric.labels,
            "timestamp_ms": metric.timestamp_ms,
            "component": metric.component,
        }
    return payload


@app.get("/metrics/snapshot")
def metrics_snapshot() -> dict[str, Any]:
    return _snapshot_to_payload(_COMPONENTS["collector"].current_snapshot)


@app.get("/metrics/timeseries/{metric_name}")
def metrics_timeseries(metric_name: str, from_ms: Optional[int] = Query(default=None, ge=0), to_ms: Optional[int] = Query(default=None, ge=0), resolution_ms: int = Query(default=5000, ge=1000, le=60000)) -> dict[str, Any]:
    try:
        metric = MetricName(metric_name)
    except Exception:
        raise HTTPException(status_code=404, detail="Unknown metric")
    now_ms = int(time.time() * 1000)
    from_ms = from_ms or now_ms - 3600 * 1000
    to_ms = to_ms or now_ms
    data_points = _COMPONENTS["metrics_store"].query_timeseries(metric, from_ms, to_ms, resolution_ms=resolution_ms)
    return {
        "metric_name": metric.value,
        "unit": "ms" if metric.value.endswith("MS") else "unitless",
        "data_points": [{"ts": ts, "value": value} for ts, value in data_points],
    }


@app.get("/metrics/financial")
def metrics_financial() -> dict[str, Any]:
    calculator = _COMPONENTS["financial"]
    sharpe = calculator.calculate_sharpe_ratio()
    drawdown = calculator.calculate_drawdown()
    win_rate = calculator.calculate_win_rate()
    with calculator._connect() as conn:
        pnl_row = conn.execute("SELECT COALESCE(SUM(COALESCE(realized_profit_usdc, 0) - COALESCE(gas_cost_usdc, 0)), 0) AS total_pnl FROM settlement_records").fetchone()
        daily_row = conn.execute("""
            SELECT COALESCE(SUM(COALESCE(realized_profit_usdc, 0) - COALESCE(gas_cost_usdc, 0)), 0) AS daily_pnl
            FROM settlement_records
            WHERE date(settled_at / 1000, 'unixepoch') = date('now')
        """).fetchone()
    return {
        "sharpe_ratio": sharpe.__dict__,
        "drawdown": drawdown.__dict__,
        "win_rate": win_rate.__dict__,
        "daily_pnl": str(Decimal(str(daily_row["daily_pnl"] or 0.0))),
        "total_pnl": str(Decimal(str(pnl_row["total_pnl"] or 0.0))),
    }


@app.get("/alerts/active")
def alerts_active() -> list[dict[str, Any]]:
    alerts = _COMPONENTS["metrics_store"].list_active_alerts()
    return [alert.__dict__ for alert in alerts]


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str) -> dict[str, Any]:
    acknowledged = _COMPONENTS["metrics_store"].acknowledge_alert(alert_id)
    if not acknowledged:
        raise HTTPException(status_code=404, detail="Alert not found")
    logger.info("ALERT_ACKNOWLEDGED: %s", alert_id)
    return {"alert_id": alert_id, "acknowledged": True}


@app.get("/system/health")
def system_health() -> dict[str, Any]:
    snapshot = _COMPONENTS["collector"].current_snapshot
    inference = next((metric.value for metric in snapshot.values() if metric.name == MetricName.INFERENCE_LATENCY_P95_MS), 0.0)
    mempool = next((metric.value for metric in snapshot.values() if metric.name == MetricName.MEMPOOL_DATA_FRESHNESS_MS), 0.0)
    oracle = next((metric.value for metric in snapshot.values() if metric.name == MetricName.ORACLE_SOURCE_COUNT), 0.0)
    execution = next((metric.value for metric in snapshot.values() if metric.name == MetricName.EXECUTION_SUCCESS_RATE), 0.0)
    risk = next((metric.value for metric in snapshot.values() if metric.name == MetricName.DRAWDOWN_FROM_PEAK_PCT), 0.0)
    trading_allowed, open_breakers = _COMPONENTS["registry"].is_trading_allowed()
    overall = "GREEN"
    if inference > 3000 or mempool > 2000 or risk >= 30 or not trading_allowed:
        overall = "RED"
    elif inference > 1500 or mempool > 800 or risk >= 15:
        overall = "YELLOW"
    return {
        "overall": overall,
        "components": {
            "inference": "GREEN" if inference < 1000 else "YELLOW" if inference < 3000 else "RED",
            "mempool": "GREEN" if mempool < 800 else "YELLOW" if mempool < 1500 else "RED",
            "oracle": "GREEN" if oracle >= 2 else "YELLOW",
            "execution": "GREEN" if execution >= 0.9 else "RED",
            "risk": "GREEN" if risk < 15 else "YELLOW" if risk < 30 else "RED",
        },
        "trading_allowed": trading_allowed,
        "open_breakers": [breaker.value for breaker in open_breakers],
        "last_successful_trade_at": _last_successful_trade_at(),
    }


def _last_successful_trade_at() -> Optional[int]:
    try:
        with _COMPONENTS["ledger"]._connect() as conn:
            row = conn.execute("SELECT MAX(settled_at) AS settled_at FROM settlement_records WHERE receipt_status = 'CONFIRMED'").fetchone()
            return int(row["settled_at"]) if row and row["settled_at"] is not None else None
    except Exception:
        return None


@app.get("/metrics/bottleneck")
def metrics_bottleneck() -> dict[str, Any]:
    report = _COMPONENTS["profiler"].profile()
    recommendations = _COMPONENTS["profiler"].generate_recommendations(report)
    slowest = report.bottleneck_stage or "unknown"
    return {
        "bottleneck_stage": slowest,
        "avg_latency_ms": report.bottleneck_p95_ms,
        "pct_of_total": report.bottleneck_pct_of_total,
        "recommendation": recommendations[0].recommendation if recommendations else "No material bottleneck detected.",
    }


@app.get("/alerts/history")
def alerts_history() -> list[dict[str, Any]]:
    return [alert.__dict__ for alert in _COMPONENTS["metrics_store"].list_active_alerts()]


@app.get("/metrics/components")
def metrics_components() -> dict[str, Any]:
    return _snapshot_to_payload(_COMPONENTS["collector"].current_snapshot)


def start_dashboard_server() -> None:
    import uvicorn

    def _run() -> None:
        uvicorn.run(app, host="0.0.0.0", port=METRICS_API_PORT, log_level="error")

    threading.Thread(target=_run, daemon=True, name="metrics-dashboard-api").start()
