"""
Signal processor that bridges TEE inference output and the structured reasoning engine.
Formats raw InferenceOutput objects into rich market context, executes the reasoning trace,
and persists the resulting audit trail.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from reasoning import ChainOfThoughtExecutor, MarketStressCalculator, ReasoningParser, TraceDB


logger = logging.getLogger(__name__)


class InferenceOutput(BaseModel):
    """Raw inference output from the TEE."""
    opportunity_id: str = Field(description="Unique opportunity ID")
    symbol: str = Field(description="Trading pair symbol")
    primary_dex: str = Field(description="Primary DEX for LONG position")
    counter_dex: str = Field(description="Counter DEX for SHORT position")
    price_a: float = Field(description="Price at primary DEX")
    price_b: float = Field(description="Price at counter DEX")
    gross_spread_percent: float = Field(description="Gross spread percentage")
    borrow_amount: float = Field(description="Amount to borrow in USDC")
    collateral_required: float = Field(description="Collateral required in USDC")
    expected_profit_usdc: float = Field(description="Expected net profit in USDC")
    confidence: float = Field(description="Model confidence 0.0-1.0")
    risk_score: float = Field(description="Risk score 0.0-1.0")
    expiry_timestamp: int = Field(description="Unix timestamp when signal expires")
    decision: str = Field(description="TEE decision: EXECUTE or SKIP")
    tee_signature: str = Field(description="TEE signature for authenticity")
    model_version: str = Field(description="Model version that generated signal")


class AgentDecision(BaseModel):
    """Decision made by the agent."""
    decision: str = Field(description="APPROVE or REJECT")
    decision_id: str = Field(description="Unique decision ID from logging")
    reasoning_summary: str = Field(description="Why the decision was made")
    key_factors: list = Field(default_factory=list, description="Key factors in decision")
    expected_profit_usdc: float = Field(description="Expected profit")
    risk_assessment: str = Field(description="Risk assessment")


@dataclass
class ProcessingResult:
    """Structured processing result that still behaves like the legacy decision object."""

    trace: Any
    decision: str
    decision_id: str
    warnings: List[str] = field(default_factory=list)

    @property
    def reasoning_summary(self) -> str:
        return self.trace.final_decision.narrative

    @property
    def key_factors(self) -> List[str]:
        return list(self.trace.risk_assessment.risk_factors)

    @property
    def expected_profit_usdc(self) -> float:
        return float(self.trace.final_decision.expected_profit_usdc)

    @property
    def risk_assessment(self) -> str:
        return self.trace.risk_assessment.narrative

    @property
    def trace_id(self) -> str:
        return self.trace.trace_id


class SignalProcessor:
    """
    Bridges TEE inference output and the LangChain agent.
    
    Responsible for:
    1. Formatting raw signals into richly detailed prompts
    2. Invoking the agent with formatted input
    3. Parsing agent output into structured decisions
    4. Error handling for malformed responses
    """
    
    def __init__(self, agent: Any):
        """
        Initialize the signal processor.
        
        Args:
            agent: Initialized FlashixAgent instance
        """
        self.agent = agent
        self.market_stress_calculator = getattr(agent, "market_stress_calculator", MarketStressCalculator())
        self.reasoning_executor = getattr(
            agent,
            "reasoning_executor",
            ChainOfThoughtExecutor(dry_run_mode=True),
        )
        self.trace_db = getattr(agent, "trace_db", TraceDB())
        self.reasoning_parser = ReasoningParser()
        self.decision_logger_tool = self._find_tool("LogExecutionDecision")

    def _find_tool(self, tool_name: str) -> Any:
        tools = getattr(self.agent, "tools", []) or []
        for tool in tools:
            if getattr(tool, "name", "") == tool_name:
                return tool
        return None

    def _recent_trade_summary(self) -> str:
        if hasattr(self.agent, "get_memory_stats"):
            try:
                stats = self.agent.get_memory_stats()
                return json.dumps(stats, ensure_ascii=True)
            except Exception:
                return "Recent performance summary unavailable."
        return "Recent performance summary unavailable."
    
    def format_signal_for_agent(self, signal: InferenceOutput) -> str:
        """
        Format an InferenceOutput into a richly detailed input prompt for the agent.
        
        Creates a human-readable message that includes all signal details so the agent
        has complete context for its analysis.
        
        Args:
            signal: InferenceOutput from TEE
        
        Returns:
            Formatted prompt string
        """
        time_to_expiry = signal.expiry_timestamp - int(time.time())
        
        prompt = (
            f"NEW ARBITRAGE SIGNAL RECEIVED:\n"
            f"- Opportunity ID: {signal.opportunity_id}\n"
            f"- Symbol: {signal.symbol}\n"
            f"- Primary DEX (LONG): {signal.primary_dex} @ ${signal.price_a:.4f}\n"
            f"- Counter DEX (SHORT): {signal.counter_dex} @ ${signal.price_b:.4f}\n"
            f"- Gross Spread: {signal.gross_spread_percent:.3f}%\n"
            f"- Borrow Amount: ${signal.borrow_amount:,.0f} USDC\n"
            f"- Collateral Required: ${signal.collateral_required:,.0f} USDC\n"
            f"- Expected Net Profit: ${signal.expected_profit_usdc:.4f} USDC\n"
            f"- Model Confidence: {signal.confidence:.3f}\n"
            f"- Risk Score: {signal.risk_score:.3f}\n"
            f"- Signal Expiry: {time_to_expiry} seconds from now\n"
            f"- TEE Signature: {signal.tee_signature[:16]}...\n"
            f"- Model Version: {signal.model_version}\n\n"
            f"Please evaluate this signal using the mandatory 5-step protocol and make an execution decision."
        )
        
        return prompt
    
    def process(self, signal: InferenceOutput) -> ProcessingResult:
        """
        Process a signal through the structured reasoning loop.

        1. Build market conditions from the current market stress snapshot
        2. Execute the chain-of-thought trace
        3. Validate arithmetic consistency and persist the trace
        4. Log approval decisions with the shared trace ID
        5. Return a structured processing result
        
        Args:
            signal: InferenceOutput from TEE
        
        Returns:
            ProcessingResult with execution approval/rejection
        
        Raises:
            No exceptions; errors result in REJECT decision with error details
        """
        try:
            market_conditions = self.market_stress_calculator.build_market_conditions(
                signal.symbol,
                recent_trade_summary=self._recent_trade_summary(),
            )
            trace = self.reasoning_executor.execute(signal, market_conditions)
            warnings = self.reasoning_parser.validate_numeric_consistency(trace)
            for warning in warnings:
                logger.warning(warning)

            self.trace_db.insert_trace(trace, warnings=warnings)

            decision_id = trace.trace_id
            if trace.final_decision.decision == "APPROVE" and self.decision_logger_tool is not None:
                logger_result = self.decision_logger_tool._run(
                    opportunity_id=signal.opportunity_id,
                    decision="APPROVE",
                    reasoning_summary=trace.final_decision.narrative,
                    decision_id=trace.trace_id,
                    reasoning=trace.final_decision.narrative,
                    confidence=float(trace.final_decision.decision_confidence),
                    expected_profit=float(trace.final_decision.expected_profit_usdc),
                    risk_factors=trace.risk_assessment.risk_factors,
                )
                try:
                    logger_payload = json.loads(logger_result)
                    if logger_payload.get("success") and logger_payload.get("decision_id"):
                        decision_id = logger_payload["decision_id"]
                except Exception:
                    logger.warning("Decision logger returned malformed payload")

            return ProcessingResult(
                trace=trace,
                decision=trace.final_decision.decision,
                decision_id=decision_id,
                warnings=warnings,
            )
        
        except Exception as e:
            return ProcessingResult(
                trace=self.reasoning_executor.parser._failed_trace(signal.opportunity_id),
                decision="REJECT",
                decision_id=signal.opportunity_id,
                warnings=[f"Unexpected error during signal processing: {e}"],
            )
