from __future__ import annotations

import json
import logging
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from fastapi import FastAPI, HTTPException, Query

from agent.settlement_monitor import LedgerStats, PostmortemRecord, RevertReason, SettlementRecord, ReceiptStatus

logger = logging.getLogger(__name__)


class SettlementLedger:
    def __init__(self, db_path: str | Path = "data/flashix.db", web3: Any = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.web3 = web3
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settlement_records (
                    record_id TEXT PRIMARY KEY,
                    opportunity_id TEXT UNIQUE,
                    correlation_id TEXT,
                    decision_id TEXT,
                    trace_id TEXT,
                    tx_hash TEXT,
                    block_number INTEGER,
                    block_timestamp INTEGER,
                    receipt_status TEXT,
                    revert_reason TEXT,
                    revert_raw_bytes TEXT,
                    gas_limit INTEGER,
                    gas_used INTEGER,
                    gas_efficiency_pct REAL,
                    effective_gas_price_gwei REAL,
                    gas_cost_usdc REAL,
                    expected_profit_usdc REAL,
                    realized_profit_usdc REAL,
                    profit_variance_usdc REAL,
                    profit_variance_pct REAL,
                    repayment_confirmed INTEGER,
                    execution_submit_ms INTEGER,
                    first_seen_in_mempool_ms INTEGER,
                    confirmed_at_ms INTEGER,
                    total_execution_latency_ms INTEGER,
                    confirmation_latency_ms INTEGER,
                    polling_attempts INTEGER,
                    settled_at INTEGER
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_settlement_status ON settlement_records(receipt_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_settlement_settled_at ON settlement_records(settled_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_settlement_revert_reason ON settlement_records(revert_reason)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_settlement_opportunity_id ON settlement_records(opportunity_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS postmortem_records (
                    postmortem_id TEXT PRIMARY KEY,
                    settlement_record_id TEXT,
                    opportunity_id TEXT,
                    failure_category TEXT,
                    root_cause TEXT,
                    contributing_factors TEXT,
                    risk_checks_that_should_have_caught_this TEXT,
                    recommended_parameter_adjustments TEXT,
                    model_retraining_triggered INTEGER,
                    generated_at INTEGER
                )
                """
            )

    def _serialize_decimal(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return value

    def insert(self, record: SettlementRecord) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT OR REPLACE INTO settlement_records (
                    record_id, opportunity_id, correlation_id, decision_id, trace_id, tx_hash,
                    block_number, block_timestamp, receipt_status, revert_reason, revert_raw_bytes,
                    gas_limit, gas_used, gas_efficiency_pct, effective_gas_price_gwei, gas_cost_usdc,
                    expected_profit_usdc, realized_profit_usdc, profit_variance_usdc, profit_variance_pct,
                    repayment_confirmed, execution_submit_ms, first_seen_in_mempool_ms, confirmed_at_ms,
                    total_execution_latency_ms, confirmation_latency_ms, polling_attempts, settled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.opportunity_id,
                    record.correlation_id,
                    record.decision_id,
                    record.trace_id,
                    record.tx_hash,
                    record.block_number,
                    record.block_timestamp,
                    record.receipt_status.value,
                    record.revert_reason.value if record.revert_reason else None,
                    record.revert_raw_bytes,
                    record.gas_limit,
                    record.gas_used,
                    record.gas_efficiency_pct,
                    record.effective_gas_price_gwei,
                    self._serialize_decimal(record.gas_cost_usdc),
                    float(record.expected_profit_usdc),
                    self._serialize_decimal(record.realized_profit_usdc),
                    self._serialize_decimal(record.profit_variance_usdc),
                    record.profit_variance_pct,
                    1 if record.repayment_confirmed else 0 if record.repayment_confirmed is not None else None,
                    record.execution_submit_ms,
                    record.first_seen_in_mempool_ms,
                    record.confirmed_at_ms,
                    record.total_execution_latency_ms,
                    record.confirmation_latency_ms,
                    record.polling_attempts,
                    record.settled_at,
                ),
            )

            postmortem = getattr(record, "_postmortem_record", None)
            if postmortem is not None:
                self._insert_postmortem(conn, postmortem)

            conn.commit()

    def _insert_postmortem(self, conn: sqlite3.Connection, postmortem: PostmortemRecord) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO postmortem_records (
                postmortem_id, settlement_record_id, opportunity_id, failure_category, root_cause,
                contributing_factors, risk_checks_that_should_have_caught_this,
                recommended_parameter_adjustments, model_retraining_triggered, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                postmortem.postmortem_id,
                postmortem.settlement_record_id,
                postmortem.opportunity_id,
                postmortem.failure_category,
                postmortem.root_cause,
                json.dumps(postmortem.contributing_factors),
                json.dumps(postmortem.risk_checks_that_should_have_caught_this),
                json.dumps(postmortem.recommended_parameter_adjustments),
                1 if postmortem.model_retraining_triggered else 0,
                postmortem.generated_at,
            ),
        )

    def insert_postmortem(self, postmortem: PostmortemRecord) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN")
            self._insert_postmortem(conn, postmortem)
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> SettlementRecord:
        return SettlementRecord(
            record_id=row["record_id"],
            opportunity_id=row["opportunity_id"],
            correlation_id=row["correlation_id"],
            decision_id=row["decision_id"],
            trace_id=row["trace_id"],
            tx_hash=row["tx_hash"],
            block_number=row["block_number"],
            block_timestamp=row["block_timestamp"],
            receipt_status=ReceiptStatus(row["receipt_status"]),
            revert_reason=RevertReason(row["revert_reason"]) if row["revert_reason"] else None,
            revert_raw_bytes=row["revert_raw_bytes"],
            gas_limit=row["gas_limit"] or 0,
            gas_used=row["gas_used"],
            gas_efficiency_pct=row["gas_efficiency_pct"],
            effective_gas_price_gwei=row["effective_gas_price_gwei"],
            gas_cost_usdc=Decimal(str(row["gas_cost_usdc"])) if row["gas_cost_usdc"] is not None else None,
            expected_profit_usdc=Decimal(str(row["expected_profit_usdc"])),
            realized_profit_usdc=Decimal(str(row["realized_profit_usdc"])) if row["realized_profit_usdc"] is not None else None,
            profit_variance_usdc=Decimal(str(row["profit_variance_usdc"])) if row["profit_variance_usdc"] is not None else None,
            profit_variance_pct=row["profit_variance_pct"],
            repayment_confirmed=bool(row["repayment_confirmed"]) if row["repayment_confirmed"] is not None else None,
            execution_submit_ms=row["execution_submit_ms"],
            first_seen_in_mempool_ms=row["first_seen_in_mempool_ms"],
            confirmed_at_ms=row["confirmed_at_ms"],
            total_execution_latency_ms=row["total_execution_latency_ms"],
            confirmation_latency_ms=row["confirmation_latency_ms"],
            polling_attempts=row["polling_attempts"],
            settled_at=row["settled_at"],
        )

    def list_records(self, limit: int = 50, offset: int = 0) -> list[SettlementRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM settlement_records ORDER BY settled_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_pnl_timeseries(self, hours: int) -> list[tuple[int, Decimal]]:
        with self._connect() as conn:
            cutoff = int(__import__("time").time() * 1000) - hours * 3600 * 1000
            rows = conn.execute(
                "SELECT settled_at, COALESCE(realized_profit_usdc, 0) AS realized_profit, COALESCE(gas_cost_usdc, 0) AS gas_cost FROM settlement_records WHERE settled_at >= ? ORDER BY settled_at ASC",
                (cutoff,),
            ).fetchall()
        cumulative = Decimal("0")
        points: list[tuple[int, Decimal]] = []
        for row in rows:
            cumulative += Decimal(str(row["realized_profit"])) - Decimal(str(row["gas_cost"]))
            points.append((int(row["settled_at"]), cumulative))
        return points

    def get_revert_analysis(self) -> dict[RevertReason, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT revert_reason, COUNT(*) AS count FROM settlement_records WHERE revert_reason IS NOT NULL GROUP BY revert_reason"
            ).fetchall()
        return {RevertReason(row["revert_reason"]): int(row["count"]) for row in rows}

    def get_gas_efficiency_trend(self, days: int) -> list[float]:
        with self._connect() as conn:
            cutoff = int(__import__("time").time() * 1000) - days * 86400 * 1000
            rows = conn.execute(
                "SELECT date(settled_at / 1000, 'unixepoch') AS day, AVG(gas_efficiency_pct) AS avg_eff FROM settlement_records WHERE settled_at >= ? AND gas_efficiency_pct IS NOT NULL GROUP BY day ORDER BY day ASC",
                (cutoff,),
            ).fetchall()
        return [float(row["avg_eff"]) for row in rows if row["avg_eff"] is not None]

    def get_ledger_stats(self) -> LedgerStats:
        with self._connect() as conn:
            row = conn.execute(
                """
                WITH base AS (
                    SELECT
                        COUNT(*) AS total_executions,
                        SUM(CASE WHEN receipt_status = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed_count,
                        SUM(CASE WHEN receipt_status = 'REVERTED' THEN 1 ELSE 0 END) AS reverted_count,
                        SUM(CASE WHEN receipt_status = 'TIMEOUT' THEN 1 ELSE 0 END) AS timeout_count,
                        COALESCE(SUM(COALESCE(realized_profit_usdc, 0)), 0) AS total_realized_profit_usdc,
                        COALESCE(SUM(COALESCE(gas_cost_usdc, 0)), 0) AS total_gas_cost_usdc,
                        COALESCE(AVG(gas_efficiency_pct), 0) AS avg_gas_efficiency_pct,
                        COALESCE(AVG(confirmation_latency_ms), 0) AS avg_confirmation_latency_ms
                    FROM settlement_records
                )
                SELECT * FROM base
                """
            ).fetchone()
            common = conn.execute(
                "SELECT revert_reason, COUNT(*) AS count FROM settlement_records WHERE revert_reason IS NOT NULL GROUP BY revert_reason ORDER BY count DESC LIMIT 1"
            ).fetchone()

        total = int(row["total_executions"] or 0)
        reverted = int(row["reverted_count"] or 0)
        most_common = RevertReason(common["revert_reason"]) if common and common["revert_reason"] else None
        return LedgerStats(
            total_executions=total,
            confirmed_count=int(row["confirmed_count"] or 0),
            reverted_count=reverted,
            timeout_count=int(row["timeout_count"] or 0),
            total_realized_profit_usdc=Decimal(str(row["total_realized_profit_usdc"] or 0)),
            total_gas_cost_usdc=Decimal(str(row["total_gas_cost_usdc"] or 0)),
            net_pnl_usdc=Decimal(str(row["total_realized_profit_usdc"] or 0)) - Decimal(str(row["total_gas_cost_usdc"] or 0)),
            avg_gas_efficiency_pct=float(row["avg_gas_efficiency_pct"] or 0),
            avg_confirmation_latency_ms=float(row["avg_confirmation_latency_ms"] or 0),
            revert_rate_pct=(float(reverted) / float(total) * 100.0) if total else 0.0,
            most_common_revert_reason=most_common,
        )

    def get_records_payload(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        records = self.list_records(limit=limit, offset=offset)
        return [
            {
                "record_id": record.record_id,
                "opportunity_id": record.opportunity_id,
                "receipt_status": record.receipt_status.value,
                "revert_reason": record.revert_reason.value if record.revert_reason else None,
                "realized_profit_usdc": str(record.realized_profit_usdc) if record.realized_profit_usdc is not None else None,
                "expected_profit_usdc": str(record.expected_profit_usdc),
                "profit_variance_pct": record.profit_variance_pct,
                "gas_used": record.gas_used,
                "settled_at": record.settled_at,
            }
            for record in records
        ]


ledger = SettlementLedger()
app = FastAPI(title="Flashix Settlement Ledger API", version="1.0.0")


@app.get("/ledger/stats")
def ledger_stats() -> dict[str, Any]:
    stats = ledger.get_ledger_stats()
    return {
        "total_executions": stats.total_executions,
        "confirmed_count": stats.confirmed_count,
        "reverted_count": stats.reverted_count,
        "timeout_count": stats.timeout_count,
        "total_realized_profit_usdc": str(stats.total_realized_profit_usdc),
        "total_gas_cost_usdc": str(stats.total_gas_cost_usdc),
        "net_pnl_usdc": str(stats.net_pnl_usdc),
        "avg_gas_efficiency_pct": stats.avg_gas_efficiency_pct,
        "avg_confirmation_latency_ms": stats.avg_confirmation_latency_ms,
        "revert_rate_pct": stats.revert_rate_pct,
        "most_common_revert_reason": stats.most_common_revert_reason.value if stats.most_common_revert_reason else None,
    }


@app.get("/ledger/records")
def ledger_records(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[dict[str, Any]]:
    return ledger.get_records_payload(limit=limit, offset=offset)


@app.get("/ledger/pnl")
def ledger_pnl(hours: int = Query(24, ge=1, le=168)) -> list[dict[str, Any]]:
    return [{"settled_at": ts, "cumulative_pnl_usdc": str(value)} for ts, value in ledger.get_pnl_timeseries(hours)]


@app.get("/ledger/reverts")
def ledger_reverts() -> dict[str, int]:
    return {reason.value: count for reason, count in ledger.get_revert_analysis().items()}
