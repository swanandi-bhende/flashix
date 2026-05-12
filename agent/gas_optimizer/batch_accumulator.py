"""Cluster approved execution requests into gas-efficient batches."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from agent.execution_engine import ExecutionRequest

from .constants import (
    BATCH_TRADE_GAS_TARGET_PER_TRADE,
    BATCH_WINDOW_MS,
    FLASHLOAN_OVERHEAD_GAS,
    MAX_BATCH_SIZE,
    MIN_BATCH_FOR_SAVINGS,
    SINGLE_TRADE_GAS_TARGET,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchSignal:
    opportunity_id: str
    primary_dex: str
    counter_dex: str
    borrow_amount_usdc: Decimal
    collateral_required_usdc: Decimal
    min_profit_usdc: Decimal
    deadline: int


@dataclass(frozen=True)
class BatchExecutionParams:
    signals: list[BatchSignal]
    borrow_token: str
    total_borrow_amount: Decimal
    batch_deadline: int
    activate_mev_burn: bool
    mev_burn_amount: Decimal


@dataclass(frozen=True)
class BatchFlushResult:
    flushed: bool
    batch_size: int
    requests: list[ExecutionRequest] = field(default_factory=list)
    total_borrow_amount_usdc: Decimal = Decimal("0")
    batch_params: Optional[BatchExecutionParams] = None
    estimated_gas_savings_pct: float = 0.0


class BatchAccumulator:
    def __init__(self) -> None:
        self.pending: list[ExecutionRequest] = []
        self.window_open_at_ms: Optional[int] = None
        self.BATCH_WINDOW_MS = BATCH_WINDOW_MS
        self.MAX_BATCH_SIZE = MAX_BATCH_SIZE
        self.MIN_BATCH_FOR_SAVINGS = MIN_BATCH_FOR_SAVINGS
        self._lock = threading.Lock()
        self._running = True
        self._timeout_thread = threading.Thread(target=self._timeout_flusher, daemon=True)
        self._timeout_thread.start()

    def submit(self, request: ExecutionRequest) -> BatchFlushResult:
        now_ms = int(time.time() * 1000)

        with self._lock:
            if not self.pending:
                self.window_open_at_ms = now_ms
                self.pending.append(request)
                return BatchFlushResult(flushed=False, batch_size=1, requests=[request])

            window_age = now_ms - (self.window_open_at_ms or now_ms)
            if window_age >= self.BATCH_WINDOW_MS:
                flushed = self._flush_locked()
                self.window_open_at_ms = now_ms
                self.pending.append(request)
                return flushed

            self.pending.append(request)
            if len(self.pending) >= self.MAX_BATCH_SIZE:
                return self._flush_locked()

            return BatchFlushResult(flushed=False, batch_size=len(self.pending), requests=list(self.pending))

    def stop(self) -> None:
        self._running = False

    def _flush_locked(self) -> BatchFlushResult:
        batch = list(self.pending)
        self.pending = []
        self.window_open_at_ms = None

        if not batch:
            return BatchFlushResult(flushed=False, batch_size=0)

        total_borrow_amount = sum((request.borrow_amount_usdc for request in batch), Decimal("0"))
        batch_signals = [
            BatchSignal(
                opportunity_id=request.opportunity_id,
                primary_dex=request.primary_dex_router,
                counter_dex=request.counter_dex_router,
                borrow_amount_usdc=request.borrow_amount_usdc,
                collateral_required_usdc=request.collateral_amount_usdc,
                min_profit_usdc=request.min_profit_usdc,
                deadline=request.deadline,
            )
            for request in batch
        ]

        batch_params = BatchExecutionParams(
            signals=batch_signals,
            borrow_token=batch[0].borrow_token,
            total_borrow_amount=total_borrow_amount,
            batch_deadline=max(request.deadline for request in batch),
            activate_mev_burn=False,
            mev_burn_amount=Decimal("0"),
        )

        savings_pct = 0.0
        if len(batch) >= MIN_BATCH_FOR_SAVINGS:
            single_cost = len(batch) * SINGLE_TRADE_GAS_TARGET
            batch_cost = FLASHLOAN_OVERHEAD_GAS + len(batch) * BATCH_TRADE_GAS_TARGET_PER_TRADE
            savings_pct = ((single_cost - batch_cost) / single_cost) * 100 if single_cost else 0.0

        _logger.info(
            "BATCH_FLUSH: size=%s, total_borrow=$%.0f, estimated_gas_savings=%.1f%%",
            len(batch),
            float(total_borrow_amount),
            savings_pct,
        )

        return BatchFlushResult(
            flushed=True,
            batch_size=len(batch),
            requests=batch,
            total_borrow_amount_usdc=total_borrow_amount,
            batch_params=batch_params,
            estimated_gas_savings_pct=savings_pct,
        )

    def _flush(self) -> BatchFlushResult:
        with self._lock:
            return self._flush_locked()

    def _timeout_flusher(self) -> None:
        while self._running:
            time.sleep(0.5)
            with self._lock:
                if self.window_open_at_ms is None or not self.pending:
                    continue

                now_ms = int(time.time() * 1000)
                if now_ms - self.window_open_at_ms >= self.BATCH_WINDOW_MS:
                    self._flush_locked()
