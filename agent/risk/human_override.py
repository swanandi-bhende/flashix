"""Human override approval gate."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from agent.risk_manager import BreakerType, HUMAN_OVERRIDE_WINDOW_SECONDS, LARGE_TRADE_THRESHOLD_USDC, OverrideResult

_logger = logging.getLogger(__name__)


class HumanOverrideGate:
    def __init__(self, registry: Any, data_dir: str = "data"):
        self.registry = registry
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.override_path = self.data_dir / "human_overrides.jsonl"

    def _log(self, payload: dict[str, Any]) -> None:
        fd = os.open(self.override_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        try:
            os.write(fd, (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def request_approval(self, opportunity_id: str, expected_profit_usdc, signal_summary: str) -> OverrideResult:
        if expected_profit_usdc < LARGE_TRADE_THRESHOLD_USDC:
            result = OverrideResult(True, "AUTO_APPROVED_BELOW_THRESHOLD", notes="Below large-trade threshold")
            self._log({"opportunity_id": opportunity_id, "expected_profit_usdc": str(expected_profit_usdc), "signal_summary": signal_summary, "result": result.method, "approved": result.approved, "timestamp": int(time.time())})
            return result

        block = (
            "\n" + "=" * 60 + "\n"
            "⚠️  LARGE TRADE PENDING APPROVAL\n"
            f"Opportunity: {opportunity_id}\n"
            f"Expected Profit: ${expected_profit_usdc:.4f} USDC\n"
            f"Signal: {signal_summary}\n"
            "Press ENTER to APPROVE or type STOP + ENTER to HALT\n"
            f"Auto-approving in {HUMAN_OVERRIDE_WINDOW_SECONDS} seconds...\n"
            + "=" * 60 + "\n"
        )
        print(block, flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(input)
            try:
                response = future.result(timeout=HUMAN_OVERRIDE_WINDOW_SECONDS)
            except concurrent.futures.TimeoutError:
                result = OverrideResult(True, "AUTO_APPROVED_TIMEOUT", notes="Timed out waiting for human override")
                self._log({"opportunity_id": opportunity_id, "expected_profit_usdc": str(expected_profit_usdc), "signal_summary": signal_summary, "result": result.method, "approved": result.approved, "timestamp": int(time.time())})
                _logger.info("HUMAN_OVERRIDE_TIMEOUT_AUTO_APPROVED: id=%s, profit=$%s", opportunity_id, expected_profit_usdc)
                return result

        if str(response).strip().upper() == "STOP":
            self.registry.open_breaker(
                BreakerType.HUMAN_OVERRIDE,
                0.0,
                opportunity_id,
                auto_reset_seconds=None,
                notes=f"Operator manually halted trade {opportunity_id}",
            )
            result = OverrideResult(False, "OPERATOR_HALTED", notes="Operator typed STOP")
        else:
            result = OverrideResult(True, "OPERATOR_APPROVED", notes="Operator approved via console")
        self._log({"opportunity_id": opportunity_id, "expected_profit_usdc": str(expected_profit_usdc), "signal_summary": signal_summary, "result": result.method, "approved": result.approved, "timestamp": int(time.time())})
        return result
