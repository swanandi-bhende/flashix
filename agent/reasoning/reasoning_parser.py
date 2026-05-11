"""Strict parsing and validation for structured reasoning traces."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .schema import (
    CostBreakdown,
    FinalDecision,
    OpportunityAnalysis,
    ProfitCalculation,
    ReasoningTrace,
    RiskAssessment,
)

logger = logging.getLogger(__name__)


class ReasoningParser:
    """Parse and validate Gemini reasoning output."""

    SECTION_NAMES = [
        "opportunity_analysis",
        "cost_breakdown",
        "profit_calculation",
        "risk_assessment",
        "final_decision",
    ]

    def parse(self, raw_response: str, opportunity_id: str) -> ReasoningTrace:
        attempts = [raw_response]
        stripped = self._strip_code_fences(raw_response)
        attempts.append(stripped)
        attempts.append(self._replace_single_quotes(stripped))
        attempts.append(self._remove_trailing_commas(self._replace_single_quotes(stripped)))
        attempts.append(self._quote_keys(self._remove_trailing_commas(self._replace_single_quotes(stripped))))

        for candidate in attempts:
            payload = self._try_json(candidate)
            if payload is not None:
                return self._build_trace(payload, opportunity_id)

        extracted = self._extract_sections(stripped)
        if extracted:
            logger.warning("PARTIAL_PARSE_WARNING missing_sections=%s", extracted.get("missing_sections", []))
            return self._build_trace(extracted["payload"], opportunity_id)

        return self._failed_trace(opportunity_id)

    def validate_numeric_consistency(self, trace: ReasoningTrace) -> List[str]:
        warnings: List[str] = []
        opportunity = trace.opportunity_analysis
        costs = trace.cost_breakdown
        profit = trace.profit_calculation

        expected_net_profit_pct = Decimal(str(opportunity.gross_spread_percent)) - Decimal(str(costs.total_cost_pct))
        if abs(expected_net_profit_pct - Decimal(str(profit.net_profit_pct))) > Decimal("0.1"):
            warnings.append(
                f"ConsistencyWarning: net_profit_pct mismatch expected={expected_net_profit_pct} actual={profit.net_profit_pct}"
            )

        expected_total_cost_usdc = (
            Decimal(str(costs.flashloan_fee_usdc))
            + Decimal(str(costs.slippage_estimate_usdc))
            + Decimal(str(costs.collateral_cost_usdc))
            + Decimal(str(costs.gas_cost_usdc))
        )
        if abs(expected_total_cost_usdc - Decimal(str(costs.total_cost_usdc))) > Decimal("0.01"):
            warnings.append(
                f"ConsistencyWarning: total_cost_usdc mismatch expected={expected_total_cost_usdc} actual={costs.total_cost_usdc}"
            )

        expected_profit_after_gas = Decimal(str(profit.net_profit_usdc)) - Decimal(str(costs.gas_cost_usdc))
        if abs(expected_profit_after_gas - Decimal(str(profit.profit_after_gas_usdc))) > Decimal("0.01"):
            warnings.append(
                f"ConsistencyWarning: profit_after_gas_usdc mismatch expected={expected_profit_after_gas} actual={profit.profit_after_gas_usdc}"
            )

        return warnings

    def _build_trace(self, payload: Dict[str, Any], opportunity_id: str) -> ReasoningTrace:
        normalized = self._normalize_payload(payload, opportunity_id)
        return ReasoningTrace.from_payload(normalized, opportunity_id=opportunity_id)

    def _normalize_payload(self, payload: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
        normalized = dict(payload)
        normalized.setdefault("trace_id", payload.get("trace_id") or opportunity_id)
        normalized.setdefault("opportunity_id", opportunity_id)
        normalized.setdefault("total_reasoning_ms", 0.0)
        normalized.setdefault("gemini_tokens_used", 0)
        normalized.setdefault("created_at", 0)
        normalized.setdefault("model_version", payload.get("model_version", "unknown"))
        for section_name in self.SECTION_NAMES:
            section = normalized.get(section_name, {})
            if isinstance(section, dict):
                section.setdefault("narrative", "")
                section.setdefault("data", {})
            else:
                section = {"narrative": "", "data": {}}
            normalized[section_name] = section
        return normalized

    def _try_json(self, raw: str) -> Optional[Dict[str, Any]]:
        try:
            candidate = raw.strip()
            if not candidate:
                return None
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def _strip_code_fences(self, raw: str) -> str:
        stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

    def _replace_single_quotes(self, raw: str) -> str:
        return re.sub(r"(?<!\\)'", '"', raw)

    def _remove_trailing_commas(self, raw: str) -> str:
        return re.sub(r",(\s*[}\]])", r"\1", raw)

    def _quote_keys(self, raw: str) -> str:
        known = [
            "trace_id",
            "opportunity_id",
            "opportunity_analysis",
            "cost_breakdown",
            "profit_calculation",
            "risk_assessment",
            "final_decision",
            "narrative",
            "data",
            "decision",
            "rejection_reason",
            "expected_profit_usdc",
            "expected_execution_time_seconds",
            "decision_confidence",
            "conditions",
            "price_dex_a",
            "price_dex_b",
            "long_dex",
            "short_dex",
            "gross_spread_usdc",
            "gross_spread_percent",
            "borrow_amount_usdc",
            "signal_confidence",
            "signal_expiry_seconds",
            "flashloan_fee_pct",
            "flashloan_fee_usdc",
            "slippage_estimate_pct",
            "slippage_estimate_usdc",
            "collateral_rate_pct_per_day",
            "collateral_cost_usdc",
            "gas_price_gwei",
            "gas_cost_usdc",
            "total_cost_pct",
            "total_cost_usdc",
            "net_profit_pct",
            "net_profit_usdc",
            "profit_after_gas_usdc",
            "break_even_spread_pct",
            "vix_equivalent_score",
            "funding_rate_volatility",
            "execution_risk",
            "liquidity_risk",
            "gas_spike_risk",
            "overall_risk",
            "risk_factors",
            "mitigating_factors",
        ]
        result = raw
        for key in known:
            result = re.sub(rf'(?<!["])(\b{re.escape(key)}\b)\s*:', rf'"{key}":', result)
        return result

    def _extract_sections(self, raw: str) -> Optional[Dict[str, Any]]:
        extracted: Dict[str, Any] = {}
        missing_sections: List[str] = []
        for section in self.SECTION_NAMES:
            match = re.search(
                rf'"?{section}"?\s*:\s*(\{{.*?\}})(?=\s*,\s*"?\w+"?\s*:|\s*\}})',
                raw,
                flags=re.DOTALL,
            )
            if not match:
                missing_sections.append(section)
                continue
            try:
                extracted[section] = json.loads(match.group(1))
            except json.JSONDecodeError:
                missing_sections.append(section)
        if not extracted:
            return None
        payload = {section: extracted.get(section, {"narrative": "PARSE_FAILED", "data": {}}) for section in self.SECTION_NAMES}
        payload.update(
            {
                "trace_id": "PARSE_FAILED",
                "opportunity_id": "PARSE_FAILED",
                "total_reasoning_ms": 0.0,
                "gemini_tokens_used": 0,
                "created_at": 0,
                "model_version": "unknown",
            }
        )
        return {"payload": payload, "missing_sections": missing_sections}

    def _failed_trace(self, opportunity_id: str) -> ReasoningTrace:
        return ReasoningTrace(
            trace_id=opportunity_id,
            opportunity_id=opportunity_id,
            opportunity_analysis=OpportunityAnalysis(
                price_dex_a=Decimal("0"),
                price_dex_b=Decimal("0"),
                long_dex="PARSE_FAILED",
                short_dex="PARSE_FAILED",
                gross_spread_usdc=Decimal("0"),
                gross_spread_percent=Decimal("0"),
                borrow_amount_usdc=Decimal("0"),
                signal_confidence=0.0,
                signal_expiry_seconds=0,
                narrative="PARSE_FAILED",
            ),
            cost_breakdown=CostBreakdown(
                flashloan_fee_pct=Decimal("0"),
                flashloan_fee_usdc=Decimal("0"),
                slippage_estimate_pct=Decimal("0"),
                slippage_estimate_usdc=Decimal("0"),
                collateral_rate_pct_per_day=Decimal("0"),
                collateral_cost_usdc=Decimal("0"),
                gas_price_gwei=0.0,
                gas_cost_usdc=Decimal("0"),
                total_cost_pct=Decimal("0"),
                total_cost_usdc=Decimal("0"),
                narrative="PARSE_FAILED",
            ),
            profit_calculation=ProfitCalculation(
                gross_spread_pct=Decimal("0"),
                total_cost_pct=Decimal("0"),
                net_profit_pct=Decimal("0"),
                net_profit_usdc=Decimal("0"),
                profit_after_gas_usdc=Decimal("0"),
                break_even_spread_pct=Decimal("0"),
                narrative="PARSE_FAILED",
            ),
            risk_assessment=RiskAssessment(
                vix_equivalent_score=0.0,
                funding_rate_volatility="LOW",
                execution_risk="HIGH",
                liquidity_risk="HIGH",
                gas_spike_risk="HIGH",
                overall_risk="HIGH",
                risk_factors=["PARSE_FAILED"],
                mitigating_factors=[],
                narrative="PARSE_FAILED",
            ),
            final_decision=FinalDecision(
                decision="REJECT",
                rejection_reason="PARSE_FAILED",
                expected_profit_usdc=Decimal("0"),
                expected_execution_time_seconds=0,
                decision_confidence=0.0,
                conditions=[],
                narrative="PARSE_FAILED",
            ),
            total_reasoning_ms=0.0,
            gemini_tokens_used=0,
            created_at=0,
            model_version="unknown",
        )
