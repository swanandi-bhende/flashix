from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
import requests

from agent.market_data.freshness_monitor import FreshnessMonitor
from agent.market_data.window_store import MarketStateWindowStore
from agent.metrics import Metric, MetricName, MetricType
from agent.metrics.alert_engine import AlertEngine
from agent.metrics.bottleneck_profiler import BottleneckProfiler
from agent.metrics.collector import MetricsCollector
from agent.metrics.financial_metrics import FinancialMetricsCalculator
from agent.metrics.metrics_store import MetricsStore
from agent.metrics.prometheus_exporter import PrometheusExporter
from agent.risk.position_watchdog import PositionWatchdog
from agent.risk.risk_registry import RiskRegistry
from agent.settlement.ledger import SettlementLedger
from agent.settlement_monitor import ReceiptStatus, SettlementRecord


class DummyRedisClient:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, str]] = {}

    def add_record(self, correlation_id: str, stage_timeline: list[dict[str, int]]) -> None:
        self._records[f"flashix:correlation:{correlation_id}"] = {
            "stage_timeline": json.dumps(stage_timeline),
            "created_at": str(stage_timeline[0]["entered_at_ms"]),
            "current_stage": stage_timeline[-1]["stage"],
        }

    def keys(self, pattern: str) -> list[str]:
        return list(self._records.keys())

    def hgetall(self, key: str) -> dict[str, str]:
        return self._records.get(key, {})


class DummyQueueManager:
    def __init__(self) -> None:
        self._client = DummyRedisClient()
        self._depths = {
            "flashix:queue:mempool_raw": 5,
            "flashix:queue:inference_requests": 3,
            "flashix:queue:agent_decisions": 2,
            "flashix:queue:execution_requests": 1,
            "flashix:queue:settlement_updates": 0,
            "flashix:queue:dead_letter": 0,
        }

    def get_queue_depths(self) -> dict[str, int]:
        return dict(self._depths)


class DummyInferenceRecorder:
    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inference_records (
                recorded_at INTEGER,
                inference_latency_ms REAL
            )
            """
        )
        self._conn.executemany(
            "INSERT INTO inference_records (recorded_at, inference_latency_ms) VALUES (?, ?)",
            [(int(time.time() * 1000) - 3000, 100.0), (int(time.time() * 1000) - 2000, 250.0), (int(time.time() * 1000) - 1000, 300.0)],
        )
        self._conn.commit()


def _make_record(*, settled_at: int, status: ReceiptStatus, realized_profit: Decimal, execution_submit_ms: int, first_seen_ms: int, total_latency_ms: int) -> SettlementRecord:
    return SettlementRecord(
        record_id=f"record-{settled_at}-{status.value}",
        opportunity_id=f"opp-{settled_at}-{status.value}",
        correlation_id=f"corr-{settled_at}-{status.value}",
        decision_id=f"dec-{settled_at}-{status.value}",
        trace_id=f"trace-{settled_at}-{status.value}",
        tx_hash=f"0x{settled_at:x}",
        block_number=123,
        block_timestamp=settled_at // 1000,
        receipt_status=status,
        revert_reason=None,
        revert_raw_bytes=None,
        gas_limit=200000,
        gas_used=180000,
        gas_efficiency_pct=90.0,
        effective_gas_price_gwei=20.0,
        gas_cost_usdc=Decimal("0"),
        expected_profit_usdc=Decimal("10"),
        realized_profit_usdc=realized_profit,
        profit_variance_usdc=Decimal("0"),
        profit_variance_pct=0.0,
        repayment_confirmed=True if status == ReceiptStatus.CONFIRMED else None,
        execution_submit_ms=execution_submit_ms,
        first_seen_in_mempool_ms=first_seen_ms,
        confirmed_at_ms=settled_at if status == ReceiptStatus.CONFIRMED else None,
        total_execution_latency_ms=total_latency_ms,
        confirmation_latency_ms=500,
        polling_attempts=1,
        settled_at=settled_at,
    )


def _build_collector(tmp_path: Path, ledger: SettlementLedger) -> MetricsCollector:
    risk_registry = RiskRegistry(data_dir=str(tmp_path / "risk"))
    window_store = MarketStateWindowStore(tracked_symbols=["BTC-USD-PERP"])
    queue_manager = DummyQueueManager()
    inference_recorder = DummyInferenceRecorder(tmp_path / "inference.db")
    position_watchdog = PositionWatchdog(registry=risk_registry, data_dir=str(tmp_path / "risk"), auto_start=False)
    freshness_monitor = FreshnessMonitor(data_dir=str(tmp_path / "freshness"))
    metrics_store = MetricsStore(db_path=tmp_path / "metrics.db")
    return MetricsCollector(
        settlement_ledger=ledger,
        risk_registry=risk_registry,
        window_store=window_store,
        queue_manager=queue_manager,
        inference_recorder=inference_recorder,
        position_watchdog=position_watchdog,
        freshness_monitor=freshness_monitor,
        metrics_store=metrics_store,
        auto_start=False,
    )


def _insert_daily_records(ledger: SettlementLedger, values: list[float], start_day_ms: int) -> None:
    for index, pnl in enumerate(values):
        ts = start_day_ms + index * 24 * 60 * 60 * 1000
        ledger.insert(
            _make_record(
                settled_at=ts,
                status=ReceiptStatus.CONFIRMED,
                realized_profit=Decimal(str(pnl)),
                execution_submit_ms=ts - 1000,
                first_seen_ms=ts - 2000,
                total_latency_ms=1000,
            )
        )


def test_success_rate_alert_triggers_at_threshold(tmp_path: Path) -> None:
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    now_ms = int(time.time() * 1000)
    for i in range(9):
        ledger.insert(
            _make_record(
                settled_at=now_ms - i * 1000,
                status=ReceiptStatus.CONFIRMED,
                realized_profit=Decimal("5"),
                execution_submit_ms=now_ms - i * 1000 - 1000,
                first_seen_ms=now_ms - i * 1000 - 2000,
                total_latency_ms=1000,
            )
        )
    ledger.insert(
        _make_record(
            settled_at=now_ms - 10_000,
            status=ReceiptStatus.REVERTED,
            realized_profit=Decimal("0"),
            execution_submit_ms=now_ms - 11_000,
            first_seen_ms=now_ms - 12_000,
            total_latency_ms=1000,
        )
    )

    collector = _build_collector(tmp_path, ledger)
    execution_metrics = collector.collect_execution_metrics()
    success_rate_metric = next(metric for metric in execution_metrics if metric.name == MetricName.EXECUTION_SUCCESS_RATE and metric.labels.get("window") == "60min")
    assert success_rate_metric.value == pytest.approx(0.9, abs=1e-6)

    ledger.insert(
        _make_record(
            settled_at=now_ms - 11_000,
            status=ReceiptStatus.REVERTED,
            realized_profit=Decimal("0"),
            execution_submit_ms=now_ms - 12_000,
            first_seen_ms=now_ms - 13_000,
            total_latency_ms=1000,
        )
    )

    snapshot = collector.collect_all()
    snapshot_map = {f"{metric.name.value}|{sorted(metric.labels.items())}": metric for metric in snapshot}
    alert_engine = AlertEngine(risk_registry=collector.risk_registry, metrics_store=collector.metrics_store)
    alerts = alert_engine.evaluate(snapshot_map)
    assert any(alert.metric_name == MetricName.EXECUTION_SUCCESS_RATE and alert.severity.value == "CRITICAL" for alert in alerts)


def test_sharpe_ratio_computed_correctly(tmp_path: Path) -> None:
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    values = [5, -2, 8, 3, -1, 6, 4, -3, 7, 2]
    start_day_ms = int(time.time() * 1000) - len(values) * 24 * 60 * 60 * 1000
    _insert_daily_records(ledger, values, start_day_ms)

    calculator = FinancialMetricsCalculator(ledger.db_path)
    result = calculator.calculate_sharpe_ratio()

    daily_returns = [value / float(Decimal("1000.0")) for value in values]
    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((value - mean_return) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
    std_return = variance ** 0.5
    risk_free_daily = (1.045) ** (1 / 365) - 1
    expected = (mean_return - risk_free_daily) / std_return * (365 ** 0.5)
    assert result.value is not None
    assert result.value == pytest.approx(expected, abs=0.001)


def test_prometheus_endpoint_reachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_PROMETHEUS_ENABLED", "false")
    ledger = SettlementLedger(db_path=tmp_path / "flashix.db")
    ledger.insert(
        _make_record(
            settled_at=int(time.time() * 1000),
            status=ReceiptStatus.CONFIRMED,
            realized_profit=Decimal("4"),
            execution_submit_ms=int(time.time() * 1000) - 1000,
            first_seen_ms=int(time.time() * 1000) - 2000,
            total_latency_ms=1000,
        )
    )
    collector = _build_collector(tmp_path, ledger)
    snapshot = {metric.name.value: metric for metric in collector.collect_all()}

    exporter = PrometheusExporter(enabled=False)
    exporter.start_server()
    exporter.sync_from_snapshot(snapshot)

    response = None
    for _ in range(30):
        try:
            response = requests.get("http://localhost:9090/metrics", timeout=1.0)
            if response.status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    assert response is not None
    assert response.status_code == 200
    body = response.text
    assert "flashix_execution_success_rate" in body
    assert "flashix_daily_pnl_usdc" in body


def test_bottleneck_profiler_identifies_slow_stage(tmp_path: Path) -> None:
    redis_client = DummyRedisClient()
    for index in range(50):
        base = int(time.time() * 1000) - index * 1000
        redis_client.add_record(
            f"corr-{index}",
            [
                {"stage": "mempool_to_filter", "entered_at_ms": base, "exited_at_ms": base + 20},
                {"stage": "filter_to_inference", "entered_at_ms": base + 20, "exited_at_ms": base + 40},
                {"stage": "inference_execution", "entered_at_ms": base + 40, "exited_at_ms": base + 3540},
                {"stage": "inference_to_agent", "entered_at_ms": base + 3540, "exited_at_ms": base + 3550},
                {"stage": "agent_reasoning", "entered_at_ms": base + 3550, "exited_at_ms": base + 3600},
                {"stage": "agent_to_execution", "entered_at_ms": base + 3600, "exited_at_ms": base + 3610},
                {"stage": "execution_submission", "entered_at_ms": base + 3610, "exited_at_ms": base + 3620},
                {"stage": "confirmation_wait", "entered_at_ms": base + 3620, "exited_at_ms": base + 3630},
                {"stage": "settlement", "entered_at_ms": base + 3630, "exited_at_ms": base + 3640},
            ],
        )

    profiler = BottleneckProfiler(redis_client=redis_client, sqlite_path=tmp_path / "trades.db", auto_start=False)
    report = profiler.profile()
    recommendations = profiler.generate_recommendations(report)
    assert report.bottleneck_stage == "inference_execution"
    assert any("InferenceWorker" in recommendation.recommendation for recommendation in recommendations)


def test_metrics_downsampling_reduces_row_count(tmp_path: Path) -> None:
    store = MetricsStore(db_path=tmp_path / "metrics.db")
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 4 * 60 * 60 * 1000
    rows = []
    for index in range(1000):
        timestamp_ms = start_ms + int(index * (2 * 60 * 60 * 1000 / 999))
        rows.append(
            Metric(
                name=MetricName.OPPS_DETECTED_PER_MIN,
                type=MetricType.RATE,
                value=float(index),
                labels={"symbol": "BTC-USD-PERP"},
                timestamp_ms=timestamp_ms,
                component="collector",
            )
        )
    store.insert_batch(rows)
    before = sqlite3.connect(store.db_path).execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert before == 1000

    store.downsample_old_data()
    after = sqlite3.connect(store.db_path).execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert 20 <= after <= 30
