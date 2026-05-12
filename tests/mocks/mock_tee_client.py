from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from typing import Any

from compute.arbitrage_analyzer import analyze


class MockTEEClient:
    def __init__(self, model_drift_pct: float = 0.0, confidence_bias: float = 0.0) -> None:
        self.model_drift_pct = model_drift_pct
        self.confidence_bias = confidence_bias
        self.stale_model_days = 0

    def set_model_drift(self, drift_pct: float) -> None:
        self.model_drift_pct = drift_pct

    def set_staleness(self, stale_model_days: int) -> None:
        self.stale_model_days = stale_model_days

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = analyze(payload)
        if "result" not in response:
            return response
        result = dict(response["result"])
        if self.model_drift_pct:
            expected = Decimal(str(result["expected_profit_usdc"]))
            result["expected_profit_usdc"] = str(expected * (Decimal("1") + Decimal(str(self.model_drift_pct)) / Decimal("100")))
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0)) - abs(self.model_drift_pct) / 200.0))
        if self.confidence_bias:
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0)) + self.confidence_bias))
        if self.stale_model_days:
            result["model_version"] = f"stale-{self.stale_model_days}d"
        return {"result": result}

    async def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.analyze(payload)

    def infer_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.analyze(payload)
