from __future__ import annotations

import math
import sqlite3
import statistics
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from agent.metrics import INITIAL_CAPITAL_USDC


@dataclass(frozen=True)
class SharpeResult:
    value: Optional[float]
    reason: Optional[str] = None
    days_available: int = 0
    days: int = 0
    mean_daily_return_pct: float = 0.0
    volatility_pct: float = 0.0


@dataclass(frozen=True)
class DrawdownResult:
    current_drawdown_pct: float
    max_drawdown_pct: float
    peak_pnl_usdc: float
    current_pnl_usdc: float
    drawdown_start_at: Optional[int]
    in_drawdown: bool


@dataclass(frozen=True)
class WinRateResult:
    win_rate: float
    wins: int
    losses: int
    avg_win_usdc: float
    avg_loss_usdc: float
    profit_factor: float


class FinancialMetricsCalculator:
    def __init__(self, db_path: str | Path = "data/flashix.db") -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def calculate_sharpe_ratio(self, lookback_days: int = 30) -> SharpeResult:
        cutoff = int(time.time() * 1000) - lookback_days * 24 * 60 * 60 * 1000
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date(settled_at / 1000, 'unixepoch') AS trading_day,
                       SUM(COALESCE(realized_profit_usdc, 0) - COALESCE(gas_cost_usdc, 0)) AS daily_pnl
                FROM settlement_records
                WHERE settled_at >= ?
                GROUP BY trading_day
                ORDER BY trading_day ASC
                """,
                (cutoff,),
            ).fetchall()
        daily_pnls = [float(row["daily_pnl"] or 0.0) for row in rows]
        if len(daily_pnls) < 5:
            return SharpeResult(value=None, reason="INSUFFICIENT_DATA", days_available=len(daily_pnls))
        daily_returns = [pnl / float(INITIAL_CAPITAL_USDC) for pnl in daily_pnls]
        mean_return = statistics.mean(daily_returns)
        std_return = statistics.stdev(daily_returns)
        if std_return == 0:
            sharpe = 0.0
        else:
            risk_free_daily = (1.045) ** (1 / 365) - 1
            sharpe = (mean_return - risk_free_daily) / std_return * math.sqrt(365)
        return SharpeResult(
            value=sharpe,
            days=len(daily_returns),
            mean_daily_return_pct=mean_return * 100,
            volatility_pct=std_return * 100,
        )

    def calculate_drawdown(self) -> DrawdownResult:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT settled_at, COALESCE(realized_profit_usdc, 0) AS realized_profit, COALESCE(gas_cost_usdc, 0) AS gas_cost
                FROM settlement_records
                WHERE receipt_status = 'CONFIRMED'
                ORDER BY settled_at ASC
                """
            ).fetchall()
        running_pnl = 0.0
        peak_pnl = 0.0
        current_drawdown = 0.0
        max_drawdown = 0.0
        drawdown_start_at: Optional[int] = None
        in_drawdown = False
        for row in rows:
            running_pnl += float(row["realized_profit"] or 0.0) - float(row["gas_cost"] or 0.0)
            if running_pnl > peak_pnl:
                peak_pnl = running_pnl
                if in_drawdown:
                    in_drawdown = False
                    drawdown_start_at = None
            current_drawdown = ((peak_pnl - running_pnl) / peak_pnl * 100.0) if peak_pnl > 0 else 0.0
            if current_drawdown > 0 and drawdown_start_at is None:
                drawdown_start_at = int(row["settled_at"])
                in_drawdown = True
            max_drawdown = max(max_drawdown, current_drawdown)
        return DrawdownResult(
            current_drawdown_pct=current_drawdown,
            max_drawdown_pct=max_drawdown,
            peak_pnl_usdc=peak_pnl,
            current_pnl_usdc=running_pnl,
            drawdown_start_at=drawdown_start_at,
            in_drawdown=current_drawdown > 0,
        )

    def calculate_win_rate(self, lookback_n: int = 100) -> WinRateResult:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT COALESCE(realized_profit_usdc, 0) AS realized_profit
                FROM settlement_records
                WHERE receipt_status = 'CONFIRMED'
                ORDER BY settled_at DESC
                LIMIT ?
                """,
                (lookback_n,),
            ).fetchall()
        profits = [float(row["realized_profit"] or 0.0) for row in rows]
        wins = [profit for profit in profits if profit > 0]
        losses = [profit for profit in profits if profit <= 0]
        total = len(profits)
        win_rate = len(wins) / total if total else 0.0
        avg_win = statistics.mean(wins) if wins else 0.0
        avg_loss = statistics.mean(losses) if losses else 0.0
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_win / gross_loss if gross_loss else float("inf")
        return WinRateResult(
            win_rate=win_rate,
            wins=len(wins),
            losses=len(losses),
            avg_win_usdc=avg_win,
            avg_loss_usdc=avg_loss,
            profit_factor=profit_factor,
        )
