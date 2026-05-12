from __future__ import annotations

import random
import time
from dataclasses import asdict
from decimal import Decimal
from uuid import uuid4

from agent.market_data import AggregatedMarketState, DataQualityLevel
from agent.execution_engine import ExecutionRequest
from tests.integration_test import MockExecutionEvent, MockReceipt


class MockBlockchain:
    def __init__(self) -> None:
        self._block_number = 0
        self._collateral_ratio = 1.6
        self._gas_spike_pct = 0.0
        self._profit_penalty_pct = 0.0
        self._delay_ms = 0
        self._block_time_seconds = 2
        self._forced_data_quality = DataQualityLevel.HIGH
        self._last_timestamp = int(time.time())

    def set_collateral_ratio(self, ratio: float) -> None:
        self._collateral_ratio = ratio

    def set_gas_spike_pct(self, spike_pct: float) -> None:
        self._gas_spike_pct = spike_pct

    def set_profit_penalty_pct(self, penalty_pct: float) -> None:
        self._profit_penalty_pct = penalty_pct

    def set_delay_ms(self, delay_ms: int) -> None:
        self._delay_ms = delay_ms

    def set_data_quality(self, quality: DataQualityLevel) -> None:
        self._forced_data_quality = quality

    def _next_block(self) -> tuple[int, int]:
        self._block_number += 1
        block_timestamp = self._last_timestamp + self._block_number * self._block_time_seconds
        return self._block_number, block_timestamp

    def simulate_execution(self, request: ExecutionRequest, market_state: AggregatedMarketState) -> MockReceipt:
        if self._delay_ms:
            time.sleep(self._delay_ms / 1000.0)

        block_number, block_timestamp = self._next_block()
        tx_hash = f"0x{uuid4().hex}"
        expected_profit = Decimal(str(request.signal.expected_profit_usdc))
        gas_used = random.randint(140_000, 175_000)

        data_quality = self._forced_data_quality if self._forced_data_quality else market_state.data_quality
        if data_quality == DataQualityLevel.UNAVAILABLE:
            return MockReceipt(
                tx_hash=tx_hash,
                block_number=block_number,
                block_timestamp=block_timestamp,
                gas_used=gas_used,
                status=0,
                revert_reason="INSUFFICIENT_COLLATERAL",
                event=None,
                raw={"status": "REVERTED", "reason": "INSUFFICIENT_COLLATERAL"},
            )

        if self._collateral_ratio < 1.5:
            return MockReceipt(
                tx_hash=tx_hash,
                block_number=block_number,
                block_timestamp=block_timestamp,
                gas_used=gas_used,
                status=0,
                revert_reason="INSUFFICIENT_COLLATERAL",
                event=None,
                raw={"status": "REVERTED", "reason": "INSUFFICIENT_COLLATERAL"},
            )

        if self._gas_spike_pct > 30.0 and random.random() < 0.4:
            return MockReceipt(
                tx_hash=tx_hash,
                block_number=block_number,
                block_timestamp=block_timestamp,
                gas_used=gas_used,
                status=0,
                revert_reason="PROFIT_BELOW_MINIMUM",
                event=None,
                raw={"status": "REVERTED", "reason": "PROFIT_BELOW_MINIMUM"},
            )

        if getattr(request.signal, "decision", "EXECUTE") == "SKIP":
            return MockReceipt(
                tx_hash=tx_hash,
                block_number=block_number,
                block_timestamp=block_timestamp,
                gas_used=gas_used,
                status=0,
                revert_reason="PROFIT_BELOW_MINIMUM",
                event=None,
                raw={"status": "REVERTED", "reason": "PROFIT_BELOW_MINIMUM"},
            )

        noise = random.gauss(0.0, 0.02)
        realized = float(expected_profit) * (1.0 - (self._profit_penalty_pct / 100.0) + noise)
        event = MockExecutionEvent(
            signal_id=request.opportunity_id,
            dex_a=request.primary_dex_router,
            dex_b=request.counter_dex_router,
            profit_realized=realized,
            gas_used=gas_used,
            timestamp=block_timestamp,
        )
        return MockReceipt(
            tx_hash=tx_hash,
            block_number=block_number,
            block_timestamp=block_timestamp,
            gas_used=gas_used,
            status=1,
            revert_reason=None,
            event=event,
            raw={"status": "CONFIRMED", "event": asdict(event)},
        )
