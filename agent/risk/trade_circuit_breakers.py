"""Trade-level and borrow-rate circuit breakers."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from decimal import Decimal
from typing import Any, Deque, Optional

from agent.risk_manager import BORROW_RATE_JUMP_THRESHOLD_PCT, BreakerType, MAX_SLIPPAGE_PCT, LimitCheck, SlippageCheck

_logger = logging.getLogger(__name__)


class SlippageCircuitBreaker:
    def __init__(self, registry: Any, data_dir: str = "data"):
        self.registry = registry
        self.data_dir = data_dir
        self.recent_slippage: Deque[float] = deque(maxlen=20)

    def check_post_execution_slippage(self, expected_profit_usdc: Decimal, realized_profit_usdc: Decimal, opportunity_id: str) -> SlippageCheck:
        if expected_profit_usdc <= 0:
            return SlippageCheck(0.0, 0.0, 0.0, False, "INVALID_EXPECTED_PROFIT")
        slippage_pct = float((expected_profit_usdc - realized_profit_usdc) / expected_profit_usdc * Decimal("100"))
        self.recent_slippage.append(slippage_pct)
        avg_5 = sum(list(self.recent_slippage)[-5:]) / min(5, len(self.recent_slippage))
        avg_20 = sum(self.recent_slippage) / len(self.recent_slippage)
        if slippage_pct > MAX_SLIPPAGE_PCT:
            self.registry.open_breaker(
                BreakerType.SLIPPAGE_EXCEEDED,
                slippage_pct,
                opportunity_id,
                auto_reset_seconds=300,
                notes=f"Trade {opportunity_id} slipped {slippage_pct:.2f}%: expected ${expected_profit_usdc}, realized ${realized_profit_usdc}",
            )
            from agent.execution_engine import ExecutionEngine

            ExecutionEngine.emergency_close(opportunity_id)
            return SlippageCheck(slippage_pct, avg_5, avg_20, True, "SLIPPAGE_THRESHOLD_EXCEEDED")
        if avg_5 > 1.5:
            self.registry.open_breaker(
                BreakerType.SLIPPAGE_EXCEEDED,
                avg_5,
                opportunity_id,
                auto_reset_seconds=300,
                notes="Sustained elevated slippage pattern detected",
            )
            return SlippageCheck(slippage_pct, avg_5, avg_20, True, "SUSTAINED_SLIPPAGE")
        return SlippageCheck(slippage_pct, avg_5, avg_20, False, "OK")


class BorrowRateCircuitBreaker:
    def __init__(self, registry: Any, lending_pool: Any = None, data_dir: str = "data", poll_interval_seconds: int = 30):
        self.registry = registry
        self.lending_pool = lending_pool
        self.data_dir = data_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.baseline_rate = self._read_rate() or 0.0
        self.current_rate = self.baseline_rate

    def _read_rate(self) -> Optional[float]:
        if self.lending_pool is None:
            return None
        try:
            raw_rate = self.lending_pool.functions.currentBorrowRate().call()
            return float(raw_rate) / 1e16 if raw_rate > 1e12 else float(raw_rate)
        except Exception:
            return None

    def start_monitoring(self) -> None:
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_borrow_rate, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        self.running = False
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=2)

    def check_current_rate(self, current_rate: Optional[float] = None) -> LimitCheck:
        rate = self._read_rate() if current_rate is None else current_rate
        if rate is None:
            return LimitCheck(True, "NO_RATE_AVAILABLE")
        self.current_rate = float(rate)
        if hasattr(self.registry, "update_market_state"):
            self.registry.update_market_state(current_borrow_rate=self.current_rate)
        rate_delta = self.current_rate - self.baseline_rate
        if rate_delta > BORROW_RATE_JUMP_THRESHOLD_PCT:
            self.registry.open_breaker(
                BreakerType.BORROW_RATE_JUMP,
                rate_delta,
                None,
                auto_reset_seconds=120,
                notes=f"Borrow rate jumped {rate_delta:.2f}% from {self.baseline_rate:.2f}% to {self.current_rate:.2f}%",
            )
            return LimitCheck(False, f"BORROW_RATE_JUMP: {rate_delta:.2f}%")
        return LimitCheck(True, "OK")

    def monitor_borrow_rate(self) -> None:
        while self.running:
            self.check_current_rate()
            time.sleep(self.poll_interval_seconds)
