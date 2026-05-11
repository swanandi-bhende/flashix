"""Typed schema for structured arbitrage reasoning traces."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from json import dumps
from typing import Any, Dict, List, Literal, Optional


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _section_payload(section: Any) -> Dict[str, Any]:
    data = asdict(section)
    narrative = data.pop("narrative")
    return {"narrative": narrative, "data": _json_safe(data)}


@dataclass
class OpportunityAnalysis:
    price_dex_a: Decimal
    price_dex_b: Decimal
    long_dex: str
    short_dex: str
    gross_spread_usdc: Decimal
    gross_spread_percent: Decimal
    borrow_amount_usdc: Decimal
    signal_confidence: float
    signal_expiry_seconds: int
    narrative: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "OpportunityAnalysis":
        data = payload.get("data", payload)
        return cls(
            price_dex_a=_decimal(data.get("price_dex_a")),
            price_dex_b=_decimal(data.get("price_dex_b")),
            long_dex=str(data.get("long_dex", "")),
            short_dex=str(data.get("short_dex", "")),
            gross_spread_usdc=_decimal(data.get("gross_spread_usdc")),
            gross_spread_percent=_decimal(data.get("gross_spread_percent")),
            borrow_amount_usdc=_decimal(data.get("borrow_amount_usdc")),
            signal_confidence=float(data.get("signal_confidence", 0.0)),
            signal_expiry_seconds=int(data.get("signal_expiry_seconds", 0)),
            narrative=str(payload.get("narrative", data.get("narrative", ""))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _section_payload(self)


@dataclass
class CostBreakdown:
    flashloan_fee_pct: Decimal
    flashloan_fee_usdc: Decimal
    slippage_estimate_pct: Decimal
    slippage_estimate_usdc: Decimal
    collateral_rate_pct_per_day: Decimal
    collateral_cost_usdc: Decimal
    gas_price_gwei: float
    gas_cost_usdc: Decimal
    total_cost_pct: Decimal
    total_cost_usdc: Decimal
    narrative: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CostBreakdown":
        data = payload.get("data", payload)
        return cls(
            flashloan_fee_pct=_decimal(data.get("flashloan_fee_pct")),
            flashloan_fee_usdc=_decimal(data.get("flashloan_fee_usdc")),
            slippage_estimate_pct=_decimal(data.get("slippage_estimate_pct")),
            slippage_estimate_usdc=_decimal(data.get("slippage_estimate_usdc")),
            collateral_rate_pct_per_day=_decimal(data.get("collateral_rate_pct_per_day")),
            collateral_cost_usdc=_decimal(data.get("collateral_cost_usdc")),
            gas_price_gwei=float(data.get("gas_price_gwei", 0.0)),
            gas_cost_usdc=_decimal(data.get("gas_cost_usdc")),
            total_cost_pct=_decimal(data.get("total_cost_pct")),
            total_cost_usdc=_decimal(data.get("total_cost_usdc")),
            narrative=str(payload.get("narrative", data.get("narrative", ""))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _section_payload(self)


@dataclass
class ProfitCalculation:
    gross_spread_pct: Decimal
    total_cost_pct: Decimal
    net_profit_pct: Decimal
    net_profit_usdc: Decimal
    profit_after_gas_usdc: Decimal
    break_even_spread_pct: Decimal
    narrative: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProfitCalculation":
        data = payload.get("data", payload)
        return cls(
            gross_spread_pct=_decimal(data.get("gross_spread_pct")),
            total_cost_pct=_decimal(data.get("total_cost_pct")),
            net_profit_pct=_decimal(data.get("net_profit_pct")),
            net_profit_usdc=_decimal(data.get("net_profit_usdc")),
            profit_after_gas_usdc=_decimal(data.get("profit_after_gas_usdc")),
            break_even_spread_pct=_decimal(data.get("break_even_spread_pct")),
            narrative=str(payload.get("narrative", data.get("narrative", ""))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _section_payload(self)


@dataclass
class RiskAssessment:
    vix_equivalent_score: float
    funding_rate_volatility: Literal["LOW", "MODERATE", "HIGH"]
    execution_risk: Literal["LOW", "MEDIUM", "HIGH"]
    liquidity_risk: Literal["LOW", "MEDIUM", "HIGH"]
    gas_spike_risk: Literal["LOW", "MEDIUM", "HIGH"]
    overall_risk: Literal["LOW", "MEDIUM", "HIGH"]
    risk_factors: List[str] = field(default_factory=list)
    mitigating_factors: List[str] = field(default_factory=list)
    narrative: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "RiskAssessment":
        data = payload.get("data", payload)
        return cls(
            vix_equivalent_score=float(data.get("vix_equivalent_score", 0.0)),
            funding_rate_volatility=str(data.get("funding_rate_volatility", "LOW")),
            execution_risk=str(data.get("execution_risk", "LOW")),
            liquidity_risk=str(data.get("liquidity_risk", "LOW")),
            gas_spike_risk=str(data.get("gas_spike_risk", "LOW")),
            overall_risk=str(data.get("overall_risk", "LOW")),
            risk_factors=list(data.get("risk_factors", [])),
            mitigating_factors=list(data.get("mitigating_factors", [])),
            narrative=str(payload.get("narrative", data.get("narrative", ""))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _section_payload(self)


@dataclass
class FinalDecision:
    decision: Literal["APPROVE", "REJECT"]
    rejection_reason: Optional[str]
    expected_profit_usdc: Decimal
    expected_execution_time_seconds: int
    decision_confidence: float
    conditions: List[str] = field(default_factory=list)
    narrative: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "FinalDecision":
        data = payload.get("data", payload)
        return cls(
            decision=str(data.get("decision", "REJECT")).upper(),
            rejection_reason=data.get("rejection_reason"),
            expected_profit_usdc=_decimal(data.get("expected_profit_usdc")),
            expected_execution_time_seconds=int(data.get("expected_execution_time_seconds", 0)),
            decision_confidence=float(data.get("decision_confidence", 0.0)),
            conditions=list(data.get("conditions", [])),
            narrative=str(payload.get("narrative", data.get("narrative", ""))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _section_payload(self)


@dataclass
class ReasoningTrace:
    trace_id: str
    opportunity_id: str
    opportunity_analysis: OpportunityAnalysis
    cost_breakdown: CostBreakdown
    profit_calculation: ProfitCalculation
    risk_assessment: RiskAssessment
    final_decision: FinalDecision
    total_reasoning_ms: float
    gemini_tokens_used: int
    created_at: int
    model_version: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], opportunity_id: Optional[str] = None) -> "ReasoningTrace":
        return cls(
            trace_id=str(payload.get("trace_id", "")),
            opportunity_id=str(payload.get("opportunity_id", opportunity_id or "")),
            opportunity_analysis=OpportunityAnalysis.from_payload(payload.get("opportunity_analysis", {})),
            cost_breakdown=CostBreakdown.from_payload(payload.get("cost_breakdown", {})),
            profit_calculation=ProfitCalculation.from_payload(payload.get("profit_calculation", {})),
            risk_assessment=RiskAssessment.from_payload(payload.get("risk_assessment", {})),
            final_decision=FinalDecision.from_payload(payload.get("final_decision", {})),
            total_reasoning_ms=float(payload.get("total_reasoning_ms", 0.0)),
            gemini_tokens_used=int(payload.get("gemini_tokens_used", 0)),
            created_at=int(payload.get("created_at", 0)),
            model_version=str(payload.get("model_version", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "opportunity_id": self.opportunity_id,
            "opportunity_analysis": self.opportunity_analysis.to_dict(),
            "cost_breakdown": self.cost_breakdown.to_dict(),
            "profit_calculation": self.profit_calculation.to_dict(),
            "risk_assessment": self.risk_assessment.to_dict(),
            "final_decision": self.final_decision.to_dict(),
            "total_reasoning_ms": self.total_reasoning_ms,
            "gemini_tokens_used": self.gemini_tokens_used,
            "created_at": self.created_at,
            "model_version": self.model_version,
        }

    def to_json(self) -> str:
        return dumps(self.to_dict(), ensure_ascii=True)


@dataclass
class StabilityReport:
    decision_consistency_pct: float
    profit_estimate_std_dev: float
    vix_score_std_dev: float
    narrative_semantic_similarity: float
    run_count: int
    decisions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
