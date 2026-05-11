"""Gemini-backed chain-of-thought executor for arbitrage reasoning."""

from __future__ import annotations

import os
import re
import time
import uuid
from decimal import Decimal
from typing import Any

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover - dependency may be unavailable in some environments
    ChatGoogleGenerativeAI = None

from .chain_of_thought_prompt import CHAIN_OF_THOUGHT_PROMPT
from .market_stress import MarketConditions
from .reasoning_parser import ReasoningParser
from .schema import (
    CostBreakdown,
    FinalDecision,
    OpportunityAnalysis,
    ProfitCalculation,
    ReasoningTrace,
    RiskAssessment,
)


class ChainOfThoughtExecutor:
    """Invoke Gemini, parse structured reasoning, and return a validated trace."""

    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
        dry_run_mode: bool = True,
    ) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.dry_run_mode = dry_run_mode
        self.parser = ReasoningParser()
        self.llm = None
        if not dry_run_mode and ChatGoogleGenerativeAI is not None:
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                convert_system_message_to_human=True,
            )

    def execute(self, signal: Any, market_conditions: MarketConditions) -> ReasoningTrace:
        start_time = time.perf_counter()
        human_turn = self._build_human_turn(signal, market_conditions)

        if self.llm is None:
            raw_response = self._build_fallback_response(signal, market_conditions)
            trace = self.parser.parse(raw_response, signal.opportunity_id)
            trace.total_reasoning_ms = (time.perf_counter() - start_time) * 1000.0
            trace.gemini_tokens_used = 0
            return trace

        prompt_value = CHAIN_OF_THOUGHT_PROMPT.invoke({"input": human_turn})
        response = self.llm.invoke(prompt_value)
        response_text = getattr(response, "content", str(response))
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        parsed_text = json_match.group(0) if json_match else response_text
        trace = self.parser.parse(parsed_text, signal.opportunity_id)
        trace.total_reasoning_ms = (time.perf_counter() - start_time) * 1000.0
        trace.gemini_tokens_used = self._extract_token_usage(response)
        trace.model_version = getattr(signal, "model_version", self.model_name)
        return trace

    def _build_human_turn(self, signal: Any, market_conditions: MarketConditions) -> str:
        expiry_seconds = max(0, int(signal.expiry_timestamp) - int(time.time()))
        return (
            f"SIGNAL DATA:\n"
            f"price_a={signal.price_a}, price_b={signal.price_b}, borrow_amount={signal.borrow_amount}, "
            f"collateral_required={signal.collateral_required}, confidence={signal.confidence}, "
            f"risk_score={signal.risk_score}, expiry_seconds={expiry_seconds}\n\n"
            f"MARKET CONDITIONS:\n"
            f"gas_price_gwei={market_conditions.gas_price_gwei}, gas_spike_detected={market_conditions.gas_spike_detected}, "
            f"funding_rate_a={market_conditions.funding_rate_a}, funding_rate_b={market_conditions.funding_rate_b}, "
            f"orderbook_depth_ratio={market_conditions.orderbook_depth_ratio}, volatility_24h={market_conditions.volatility_24h}, "
            f"vix_equivalent={market_conditions.vix_equivalent_score}\n\n"
            f"RECENT PERFORMANCE:\n{market_conditions.recent_trade_summary}\n\n"
            f"Now reason through all five sections and return your complete analysis as a single JSON object."
        )

    def _build_fallback_response(self, signal: Any, market_conditions: MarketConditions) -> str:
        borrow_amount = Decimal(str(signal.borrow_amount))
        collateral_required = Decimal(str(signal.collateral_required))
        price_a = Decimal(str(signal.price_a))
        price_b = Decimal(str(signal.price_b))
        spread_pct = (abs(price_a - price_b) / max(min(price_a, price_b), Decimal("0.0001"))) * Decimal("100")
        gross_spread_usdc = borrow_amount * spread_pct / Decimal("100")
        flashloan_fee_usdc = borrow_amount * Decimal("0.0009")
        flashloan_fee_pct = Decimal("0.09")
        if borrow_amount < Decimal("10000"):
            slippage_rate = Decimal("0.002")
            slippage_pct = Decimal("0.20")
        elif borrow_amount <= Decimal("50000"):
            slippage_rate = Decimal("0.0035")
            slippage_pct = Decimal("0.35")
        else:
            slippage_rate = Decimal("0.005")
            slippage_pct = Decimal("0.50")
        slippage_usdc = borrow_amount * slippage_rate
        collateral_rate_pct_per_day = Decimal("0.15")
        estimated_hold_hours = Decimal("10")
        collateral_cost_usdc = collateral_required * Decimal("0.0015") / Decimal("24") * estimated_hold_hours
        gas_cost_usdc = Decimal(str(market_conditions.gas_price_gwei)) * Decimal("1e-9") * Decimal("180000") * Decimal(str(self._eth_price_usdc()))
        total_cost_usdc = flashloan_fee_usdc + slippage_usdc + collateral_cost_usdc + gas_cost_usdc
        total_cost_pct = total_cost_usdc / max(borrow_amount, Decimal("0.0001")) * Decimal("100")
        net_profit_pct = spread_pct - total_cost_pct
        net_profit_usdc = borrow_amount * net_profit_pct / Decimal("100")
        profit_after_gas_usdc = net_profit_usdc - gas_cost_usdc
        break_even_spread_pct = total_cost_pct
        vix_label = self._risk_label(market_conditions.vix_equivalent_score)
        decision = "APPROVE"
        rejection_reason = None
        if float(signal.confidence) < 0.75:
            decision = "REJECT"
            rejection_reason = "Confidence below threshold"
        elif profit_after_gas_usdc <= Decimal("2"):
            decision = "REJECT"
            rejection_reason = "Expected profit after gas below threshold"
        elif market_conditions.gas_spike_detected:
            decision = "REJECT"
            rejection_reason = "Gas spike detected"
        else:
            expiry_seconds = max(0, int(signal.expiry_timestamp) - int(time.time()))
            if expiry_seconds <= 5:
                decision = "REJECT"
                rejection_reason = "Signal expiry too close"

        opportunity_analysis = OpportunityAnalysis(
            price_dex_a=price_a,
            price_dex_b=price_b,
            long_dex=str(getattr(signal, "primary_dex", "DEX_A")),
            short_dex=str(getattr(signal, "counter_dex", "DEX_B")),
            gross_spread_usdc=gross_spread_usdc,
            gross_spread_percent=spread_pct,
            borrow_amount_usdc=borrow_amount,
            signal_confidence=float(signal.confidence),
            signal_expiry_seconds=max(0, int(signal.expiry_timestamp) - int(time.time())),
            narrative=(
                f"Signal shows {spread_pct.quantize(Decimal('0.01'))}% price discrepancy between "
                f"{getattr(signal, 'primary_dex', 'DEX_A')} (long at ${price_a}) and "
                f"{getattr(signal, 'counter_dex', 'DEX_B')} (short at ${price_b}). "
                f"Borrow amount: ${borrow_amount} USDC. Signal confidence: {signal.confidence}. "
                f"Expires in {max(0, int(signal.expiry_timestamp) - int(time.time()))} seconds."
            ),
        )
        cost_breakdown = CostBreakdown(
            flashloan_fee_pct=flashloan_fee_pct,
            flashloan_fee_usdc=flashloan_fee_usdc,
            slippage_estimate_pct=slippage_pct,
            slippage_estimate_usdc=slippage_usdc,
            collateral_rate_pct_per_day=collateral_rate_pct_per_day,
            collateral_cost_usdc=collateral_cost_usdc,
            gas_price_gwei=float(market_conditions.gas_price_gwei),
            gas_cost_usdc=gas_cost_usdc,
            total_cost_pct=total_cost_pct,
            total_cost_usdc=total_cost_usdc,
            narrative=(
                f"Flashloan fee: 0.09% = ${flashloan_fee_usdc.quantize(Decimal('0.01'))}. "
                f"Slippage: {slippage_pct}% = ${slippage_usdc.quantize(Decimal('0.01'))}. "
                f"Collateral cost: ${collateral_cost_usdc.quantize(Decimal('0.01'))}. "
                f"Gas: ${gas_cost_usdc.quantize(Decimal('0.01'))}. "
                f"Total cost: {total_cost_pct.quantize(Decimal('0.01'))}% = ${total_cost_usdc.quantize(Decimal('0.01'))}."
            ),
        )
        profit_calculation = ProfitCalculation(
            gross_spread_pct=spread_pct,
            total_cost_pct=total_cost_pct,
            net_profit_pct=net_profit_pct,
            net_profit_usdc=net_profit_usdc,
            profit_after_gas_usdc=profit_after_gas_usdc,
            break_even_spread_pct=break_even_spread_pct,
            narrative=(
                f"Gross spread: {spread_pct.quantize(Decimal('0.01'))}%. Total cost: {total_cost_pct.quantize(Decimal('0.01'))}%. "
                f"Net profit: {net_profit_pct.quantize(Decimal('0.01'))}% = ${net_profit_usdc.quantize(Decimal('0.01'))}."
            ),
        )
        risk_assessment = RiskAssessment(
            vix_equivalent_score=float(market_conditions.vix_equivalent_score),
            funding_rate_volatility=market_conditions.funding_rate_volatility,
            execution_risk=market_conditions.execution_risk,
            liquidity_risk=market_conditions.liquidity_risk,
            gas_spike_risk=market_conditions.gas_spike_risk,
            overall_risk=market_conditions.overall_risk,
            risk_factors=["gas_spike_detected"] if market_conditions.gas_spike_detected else [],
            mitigating_factors=["spread_above_threshold"] if spread_pct > Decimal("2") else [],
            narrative=(
                f"VIX-equivalent: {market_conditions.vix_equivalent_score}/100 ({vix_label}). "
                f"Funding rate volatility: {market_conditions.funding_rate_volatility}. "
                f"Execution risk: {market_conditions.execution_risk}. "
                f"Liquidity risk: {market_conditions.liquidity_risk}. "
                f"Gas spike risk: {market_conditions.gas_spike_risk}."
            ),
        )
        final_decision = FinalDecision(
            decision=decision,
            rejection_reason=rejection_reason,
            expected_profit_usdc=profit_after_gas_usdc,
            expected_execution_time_seconds=8,
            decision_confidence=float(signal.confidence),
            conditions=["signal_valid", "profit_positive", "gas_stable"],
            narrative=(
                f"APPROVE execution. Expected profit after gas: ${profit_after_gas_usdc.quantize(Decimal('0.01'))}. Expected execution time: 8 seconds."
                if decision == "APPROVE"
                else f"REJECT execution. Reason: {rejection_reason}."
            ),
        )
        return ReasoningTrace(
            trace_id=str(uuid.uuid4()),
            opportunity_id=str(signal.opportunity_id),
            opportunity_analysis=opportunity_analysis,
            cost_breakdown=cost_breakdown,
            profit_calculation=profit_calculation,
            risk_assessment=risk_assessment,
            final_decision=final_decision,
            total_reasoning_ms=0.0,
            gemini_tokens_used=0,
            created_at=int(time.time()),
            model_version=str(getattr(signal, "model_version", self.model_name)),
        ).to_json()

    def _risk_label(self, score: float) -> str:
        if score <= 33:
            return "LOW"
        if score <= 66:
            return "MODERATE"
        return "HIGH"

    def _eth_price_usdc(self) -> float:
        return float(os.getenv("ETH_PRICE_USDC", "600"))

    def _extract_token_usage(self, response: Any) -> int:
        for attr in ("usage_metadata", "response_metadata"):
            metadata = getattr(response, attr, None)
            if isinstance(metadata, dict):
                total = metadata.get("total_tokens") or metadata.get("token_count")
                if isinstance(total, int):
                    return total
                prompt_tokens = metadata.get("prompt_token_count", 0)
                completion_tokens = metadata.get("candidates_token_count", 0)
                if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                    return prompt_tokens + completion_tokens
        return 0
