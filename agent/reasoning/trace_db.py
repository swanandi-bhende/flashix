"""SQLite persistence for reasoning traces."""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .schema import ReasoningTrace


class TraceDB:
    """Manage reasoning traces in a local SQLite database."""

    def __init__(self, db_path: str = "data/reasoning_traces.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reasoning_traces (
                    trace_id TEXT PRIMARY KEY,
                    opportunity_id TEXT UNIQUE,
                    decision TEXT,
                    rejection_reason TEXT,
                    gross_spread_pct REAL,
                    total_cost_pct REAL,
                    net_profit_pct REAL,
                    net_profit_usdc REAL,
                    vix_equivalent_score REAL,
                    execution_risk TEXT,
                    overall_risk TEXT,
                    signal_confidence REAL,
                    gas_price_gwei REAL,
                    flashloan_fee_usdc REAL,
                    slippage_usdc REAL,
                    gas_cost_usdc REAL,
                    opportunity_analysis_narrative TEXT,
                    cost_breakdown_narrative TEXT,
                    profit_calculation_narrative TEXT,
                    risk_assessment_narrative TEXT,
                    final_decision_narrative TEXT,
                    full_trace_json TEXT,
                    numeric_consistency_warnings TEXT,
                    total_reasoning_ms REAL,
                    gemini_tokens_used INTEGER,
                    created_at INTEGER
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_traces_opportunity_id ON reasoning_traces(opportunity_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_traces_decision ON reasoning_traces(decision)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_traces_created_at ON reasoning_traces(created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_traces_vix ON reasoning_traces(vix_equivalent_score)")
            connection.commit()

    def insert_trace(self, trace: ReasoningTrace, warnings: Optional[List[str]] = None) -> None:
        warnings = warnings or []
        payload = trace.to_dict()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN")
                connection.execute(
                    """
                    INSERT OR REPLACE INTO reasoning_traces (
                        trace_id,
                        opportunity_id,
                        decision,
                        rejection_reason,
                        gross_spread_pct,
                        total_cost_pct,
                        net_profit_pct,
                        net_profit_usdc,
                        vix_equivalent_score,
                        execution_risk,
                        overall_risk,
                        signal_confidence,
                        gas_price_gwei,
                        flashloan_fee_usdc,
                        slippage_usdc,
                        gas_cost_usdc,
                        opportunity_analysis_narrative,
                        cost_breakdown_narrative,
                        profit_calculation_narrative,
                        risk_assessment_narrative,
                        final_decision_narrative,
                        full_trace_json,
                        numeric_consistency_warnings,
                        total_reasoning_ms,
                        gemini_tokens_used,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace.trace_id,
                        trace.opportunity_id,
                        trace.final_decision.decision,
                        trace.final_decision.rejection_reason,
                        float(trace.profit_calculation.gross_spread_pct),
                        float(trace.cost_breakdown.total_cost_pct),
                        float(trace.profit_calculation.net_profit_pct),
                        float(trace.profit_calculation.net_profit_usdc),
                        float(trace.risk_assessment.vix_equivalent_score),
                        trace.risk_assessment.execution_risk,
                        trace.risk_assessment.overall_risk,
                        float(trace.opportunity_analysis.signal_confidence),
                        float(trace.cost_breakdown.gas_price_gwei),
                        float(trace.cost_breakdown.flashloan_fee_usdc),
                        float(trace.cost_breakdown.slippage_estimate_usdc),
                        float(trace.cost_breakdown.gas_cost_usdc),
                        trace.opportunity_analysis.narrative,
                        trace.cost_breakdown.narrative,
                        trace.profit_calculation.narrative,
                        trace.risk_assessment.narrative,
                        trace.final_decision.narrative,
                        json.dumps(payload, ensure_ascii=True),
                        json.dumps(warnings, ensure_ascii=True),
                        float(trace.total_reasoning_ms),
                        int(trace.gemini_tokens_used),
                        int(trace.created_at),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def get_trace(self, opportunity_id: str) -> Optional[ReasoningTrace]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT full_trace_json FROM reasoning_traces WHERE opportunity_id = ? LIMIT 1",
                (opportunity_id,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["full_trace_json"])
            return ReasoningTrace.from_payload(payload, opportunity_id=opportunity_id)

    def get_recent_traces(
        self,
        limit: int,
        decision_filter: Optional[str] = None,
        min_profit: Optional[float] = None,
        since_timestamp: Optional[int] = None,
    ) -> List[ReasoningTrace]:
        query = "SELECT full_trace_json FROM reasoning_traces WHERE 1=1"
        params: List[Any] = []
        if decision_filter:
            query += " AND decision = ?"
            params.append(decision_filter.upper())
        if min_profit is not None:
            query += " AND net_profit_usdc >= ?"
            params.append(float(min_profit))
        if since_timestamp is not None:
            query += " AND created_at >= ?"
            params.append(int(since_timestamp))
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        traces: List[ReasoningTrace] = []
        for row in rows:
            payload = json.loads(row["full_trace_json"])
            traces.append(ReasoningTrace.from_payload(payload, opportunity_id=payload.get("opportunity_id", "")))
        return traces

    def get_reasoning_stats(self) -> Dict[str, Any]:
        with self._connect() as connection:
            total_traces = connection.execute("SELECT COUNT(*) FROM reasoning_traces").fetchone()[0]
            approve_count = connection.execute("SELECT COUNT(*) FROM reasoning_traces WHERE decision = 'APPROVE'").fetchone()[0]
            reject_count = connection.execute("SELECT COUNT(*) FROM reasoning_traces WHERE decision = 'REJECT'").fetchone()[0]
            avg_net_profit_approved = connection.execute(
                "SELECT AVG(net_profit_usdc) FROM reasoning_traces WHERE decision = 'APPROVE'"
            ).fetchone()[0]
            avg_vix_approved = connection.execute(
                "SELECT AVG(vix_equivalent_score) FROM reasoning_traces WHERE decision = 'APPROVE'"
            ).fetchone()[0]
            avg_reasoning_ms = connection.execute("SELECT AVG(total_reasoning_ms) FROM reasoning_traces").fetchone()[0]
            rejection_rows = connection.execute(
                """
                SELECT rejection_reason, COUNT(*) AS count
                FROM reasoning_traces
                WHERE decision = 'REJECT' AND rejection_reason IS NOT NULL AND rejection_reason != ''
                GROUP BY rejection_reason
                ORDER BY count DESC
                LIMIT 1
                """
            ).fetchone()
        return {
            "total_traces": int(total_traces or 0),
            "approve_count": int(approve_count or 0),
            "reject_count": int(reject_count or 0),
            "avg_net_profit_approved": float(avg_net_profit_approved or 0.0),
            "avg_vix_approved": float(avg_vix_approved or 0.0),
            "avg_reasoning_ms": float(avg_reasoning_ms or 0.0),
            "most_common_rejection_reason": rejection_rows["rejection_reason"] if rejection_rows else None,
        }
