"""
Signal processor that bridges TEE inference output and the LangChain agent.
Formats raw InferenceOutput objects into structured inputs for the agent's reasoning loop.
"""

import json
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
    
    def process(self, signal: InferenceOutput) -> AgentDecision:
        """
        Process a signal through the agent's reasoning loop.
        
        1. Format signal into agent input
        2. Invoke agent with formatting handling
        3. Parse agent output into structured decision
        4. Validate decision structure
        5. Return structured AgentDecision
        
        Args:
            signal: InferenceOutput from TEE
        
        Returns:
            AgentDecision with execution approval/rejection
        
        Raises:
            No exceptions; errors result in REJECT decision with error details
        """
        try:
            # Format signal for agent
            formatted_signal = self.format_signal_for_agent(signal)
            
            # Invoke agent
            agent_response = self.agent.invoke(formatted_signal)
            
            # Handle potential errors from agent
            if "error" in agent_response:
                return AgentDecision(
                    decision="REJECT",
                    decision_id="",
                    reasoning_summary=f"Agent error: {agent_response['error']}",
                    key_factors=["AGENT_EXECUTION_ERROR"],
                    expected_profit_usdc=0.0,
                    risk_assessment="Agent failed to process signal; rejected as precaution"
                )
            
            # Extract and parse agent output
            output_text = agent_response.get("output", "{}")
            
            # Try to extract JSON from output (agent might wrap it in markdown)
            if "```json" in output_text:
                json_start = output_text.find("```json") + 7
                json_end = output_text.find("```", json_start)
                if json_end > json_start:
                    output_text = output_text[json_start:json_end].strip()
            
            # Parse JSON response
            try:
                response_dict = json.loads(output_text)
            except json.JSONDecodeError:
                # Fallback: agent output was not valid JSON
                return AgentDecision(
                    decision="REJECT",
                    decision_id="",
                    reasoning_summary="Agent output was not valid JSON",
                    key_factors=["INVALID_JSON_RESPONSE"],
                    expected_profit_usdc=0.0,
                    risk_assessment="Agent produced malformed output; signal rejected"
                )
            
            # Validate required fields
            required_fields = ["decision", "reasoning_summary", "risk_assessment"]
            missing_fields = [f for f in required_fields if f not in response_dict]
            
            if missing_fields:
                return AgentDecision(
                    decision="REJECT",
                    decision_id="",
                    reasoning_summary=f"Agent output missing fields: {missing_fields}",
                    key_factors=["INCOMPLETE_RESPONSE"],
                    expected_profit_usdc=0.0,
                    risk_assessment="Agent output was incomplete; signal rejected"
                )
            
            # Build and return AgentDecision
            decision = AgentDecision(
                decision=response_dict.get("decision", "REJECT").upper(),
                decision_id=response_dict.get("decision_id", ""),
                reasoning_summary=response_dict.get("reasoning_summary", ""),
                key_factors=response_dict.get("key_factors", []),
                expected_profit_usdc=response_dict.get("expected_profit_usdc", 0.0),
                risk_assessment=response_dict.get("risk_assessment", "")
            )
            
            return decision
        
        except Exception as e:
            # Catch-all for any unexpected errors
            return AgentDecision(
                decision="REJECT",
                decision_id="",
                reasoning_summary=f"Unexpected error during signal processing: {e}",
                key_factors=["UNEXPECTED_ERROR"],
                expected_profit_usdc=0.0,
                risk_assessment="Critical error during processing; signal rejected for safety"
            )
