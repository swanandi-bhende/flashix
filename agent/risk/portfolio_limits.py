"""Portfolio limit enforcement."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from agent.risk_manager import DAILY_LOSS_CAP_USDC, BreakerType, CircuitBreakerState, LimitCheck, MAX_COLLATERAL_RATIO, MAX_CONCURRENT_POSITIONS, MIN_COLLATERAL_RATIO

_logger = logging.getLogger(__name__)


class PortfolioLimitsEnforcer:
    def __init__(self, registry: Any, data_dir: str = "data"):
        self.registry = registry
        self.data_dir = data_dir
        self._midnight_thread: Optional[threading.Thread] = None
        self._midnight_running = False

    def check_concurrent_positions(self) -> LimitCheck:
        with self.registry.lock:
            if self.registry.concurrent_positions < MAX_CONCURRENT_POSITIONS:
                return LimitCheck(True, "OK")
            self.registry.open_breaker(
                BreakerType.MAX_CONCURRENT_POSITIONS,
                float(self.registry.concurrent_positions),
                None,
                auto_reset_seconds=None,
                notes=f"{self.registry.concurrent_positions} positions open, max is {MAX_CONCURRENT_POSITIONS}",
            )
            return LimitCheck(False, "MAX_CONCURRENT_POSITIONS")

    def on_position_opened(self, opportunity_id: str) -> None:
        with self.registry.lock:
            self.registry.concurrent_positions += 1
            _logger.info("POSITION_OPENED: id=%s, total_open=%s", opportunity_id, self.registry.concurrent_positions)

    def on_position_closed(self, opportunity_id: str, pnl_usdc: Decimal) -> None:
        with self.registry.lock:
            self.registry.concurrent_positions = max(0, self.registry.concurrent_positions - 1)
            self.registry.daily_pnl += pnl_usdc
            _logger.info("POSITION_CLOSED: id=%s, pnl=$%s, daily_total=$%s", opportunity_id, pnl_usdc, self.registry.daily_pnl)
            if self.registry.daily_pnl <= DAILY_LOSS_CAP_USDC:
                self.registry.open_breaker(
                    BreakerType.DAILY_LOSS_CAP,
                    float(self.registry.daily_pnl),
                    opportunity_id,
                    auto_reset_seconds=None,
                    notes=f"Daily pnl {self.registry.daily_pnl} breached cap {DAILY_LOSS_CAP_USDC}",
                )

    def check_collateral_ratio(self, borrow_amount: Decimal, collateral_provided: Decimal) -> LimitCheck:
        if borrow_amount <= 0:
            return LimitCheck(False, "INVALID_BORROW_AMOUNT")
        ratio = float(collateral_provided / borrow_amount)
        with self.registry.lock:
            self.registry.current_collateral_ratio = ratio
        if ratio < MIN_COLLATERAL_RATIO:
            return LimitCheck(False, "BELOW_MIN_COLLATERAL")
        if ratio > MAX_COLLATERAL_RATIO:
            self.registry.open_breaker(
                BreakerType.MAX_COLLATERAL_RATIO,
                ratio,
                None,
                auto_reset_seconds=None,
                notes=f"Collateral ratio {ratio:.2f}x exceeds ceiling {MAX_COLLATERAL_RATIO}x",
            )
            return LimitCheck(False, "MAX_COLLATERAL_RATIO")
        return LimitCheck(True, "OK")

    def _reset_daily_pnl_once(self, now: Optional[datetime] = None) -> None:
        with self.registry.lock:
            self.registry.daily_pnl = Decimal("0")
            if self.registry.breaker_states.get(BreakerType.DAILY_LOSS_CAP) == CircuitBreakerState.OPEN:
                self.registry.close_breaker(BreakerType.DAILY_LOSS_CAP, "CONDITION_CLEARED")

    def reset_daily_pnl_at_midnight(self) -> None:
        if self._midnight_running:
            return
        self._midnight_running = True

        def _loop() -> None:
            while self._midnight_running:
                now = datetime.utcnow()
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_seconds = max(0.0, (next_midnight - now).total_seconds())
                threading.Event().wait(sleep_seconds)
                self._reset_daily_pnl_once(next_midnight)

        self._midnight_thread = threading.Thread(target=_loop, daemon=True)
        self._midnight_thread.start()
