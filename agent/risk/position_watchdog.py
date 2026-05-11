"""Position timeout watchdog."""

from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from agent.risk_manager import BreakerType, POSITION_TIMEOUT_SECONDS, PositionRecord

_logger = logging.getLogger(__name__)


class PositionWatchdog:
    def __init__(self, registry: Any, data_dir: str = "data", auto_start: bool = True):
        self.registry = registry
        self.data_dir = data_dir
        self.open_positions: Dict[str, PositionRecord] = {}
        self.timed_out_positions: Dict[str, PositionRecord] = {}
        self.positions_closed_normally = 0
        self.running = False
        self.watchdog_thread: Optional[threading.Thread] = None
        if auto_start:
            self.start()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.watchdog_thread is not None:
            self.watchdog_thread.join(timeout=2)

    def register_position(self, opportunity_id: str, tx_hash: str, borrow_amount: Decimal) -> None:
        opened_at = int(time.time())
        record = PositionRecord(
            opportunity_id=opportunity_id,
            opened_at=opened_at,
            borrow_amount=borrow_amount,
            expected_close_at=opened_at + POSITION_TIMEOUT_SECONDS,
            tx_hash=tx_hash,
        )
        with self.registry.lock:
            self.open_positions[opportunity_id] = record

    def deregister_position(self, opportunity_id: str) -> None:
        with self.registry.lock:
            if opportunity_id in self.open_positions:
                self.open_positions.pop(opportunity_id, None)
                self.positions_closed_normally += 1

    def _watchdog_iteration(self) -> None:
        now = int(time.time())
        expired = []
        with self.registry.lock:
            for opportunity_id, record in list(self.open_positions.items()):
                age = now - record.opened_at
                if age >= POSITION_TIMEOUT_SECONDS:
                    expired.append((opportunity_id, record, age))
        for opportunity_id, record, age in expired:
            _logger.critical(
                "POSITION_TIMEOUT_TRIGGERED: id=%s, age=%ss, borrow_amount=$%s",
                opportunity_id,
                age,
                record.borrow_amount,
            )
            self.registry.open_breaker(
                BreakerType.POSITION_TIMEOUT,
                float(age),
                opportunity_id,
                auto_reset_seconds=None,
                notes=f"Position {opportunity_id} timed out after {age}s",
            )
            from agent.execution_engine import ExecutionEngine

            ExecutionEngine.emergency_close(opportunity_id)
            with self.registry.lock:
                self.timed_out_positions[opportunity_id] = record
                self.open_positions.pop(opportunity_id, None)

    def _watchdog_loop(self) -> None:
        while self.running:
            self._watchdog_iteration()
            time.sleep(2)
