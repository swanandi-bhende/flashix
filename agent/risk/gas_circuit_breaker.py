"""Gas spike circuit breaker."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Optional, Tuple

from agent.risk_manager import BreakerType, CircuitBreakerState, GAS_SPIKE_THRESHOLD_PCT, GAS_SPIKE_WINDOW_SECONDS, SpikeCheckResult

_logger = logging.getLogger(__name__)


class GasCircuitBreaker:
    def __init__(self, registry: Any, web3: Any = None, data_dir: str = "data", sample_provider: Optional[Callable[[], float]] = None):
        self.registry = registry
        self.web3 = web3
        self.sample_provider = sample_provider
        self.samples: Deque[Tuple[int, float]] = deque(maxlen=60)
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.data_dir = data_dir

    def start_monitoring(self) -> None:
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        self.running = False
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=2)

    def _read_fee(self) -> Optional[float]:
        if self.sample_provider is not None:
            return float(self.sample_provider())
        if self.web3 is None:
            return None
        try:
            block = self.web3.eth.get_block("latest")
            base_fee = block.get("baseFeePerGas") if isinstance(block, dict) else getattr(block, "baseFeePerGas", None)
            if base_fee is None:
                return None
            return float(base_fee) / 1e9
        except Exception:
            return None

    def _monitor_loop(self) -> None:
        while self.running:
            self.record_sample()
            self.check_auto_reset()
            time.sleep(1)

    def record_sample(self, base_fee_gwei: Optional[float] = None) -> None:
        fee = float(base_fee_gwei if base_fee_gwei is not None else self._read_fee() or 0.0)
        timestamp = int(time.time())
        self.samples.append((timestamp, fee))
        if hasattr(self.registry, "update_market_state"):
            self.registry.update_market_state(gas_price_gwei=fee)

    def check_spike(self) -> SpikeCheckResult:
        now = int(time.time())
        window = [(timestamp, fee) for timestamp, fee in self.samples if now - timestamp <= GAS_SPIKE_WINDOW_SECONDS]
        if len(window) < 5:
            return SpikeCheckResult(False, reason="INSUFFICIENT_HISTORY", window_size=len(window))
        baseline_fee = min(fee for _, fee in window)
        current_fee = window[-1][1]
        if baseline_fee <= 0:
            return SpikeCheckResult(False, reason="BASELINE_ZERO", baseline_fee_gwei=baseline_fee, current_fee_gwei=current_fee, window_size=len(window))
        spike_pct = (current_fee - baseline_fee) / baseline_fee * 100
        if spike_pct > GAS_SPIKE_THRESHOLD_PCT:
            self.registry.open_breaker(
                BreakerType.GAS_SPIKE,
                spike_pct,
                None,
                auto_reset_seconds=60,
                notes=f"Gas rose {spike_pct:.1f}% in 30s: {baseline_fee:.1f} -> {current_fee:.1f} gwei",
            )
            return SpikeCheckResult(True, spike_pct=spike_pct, baseline_fee_gwei=baseline_fee, current_fee_gwei=current_fee, window_size=len(window))
        return SpikeCheckResult(False, spike_pct=spike_pct, baseline_fee_gwei=baseline_fee, current_fee_gwei=current_fee, window_size=len(window), reason="NO_SPIKE")

    def check_auto_reset(self) -> None:
        if self.registry.breaker_states.get(BreakerType.GAS_SPIKE) != CircuitBreakerState.OPEN:
            return
        if len(self.samples) < 5:
            return
        average_fee = sum(fee for _, fee in self.samples) / len(self.samples)
        current_fee = self.samples[-1][1]
        if average_fee <= 0:
            return
        if abs(current_fee - average_fee) / average_fee <= 0.10:
            self.registry.close_breaker(BreakerType.GAS_SPIKE, "CONDITION_CLEARED")
            _logger.info("GAS_SPIKE_RESOLVED: fee normalized to %.1f gwei", current_fee)
