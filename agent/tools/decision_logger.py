"""
Tool 4: LogExecutionDecision
Logs execution decisions immutably for audit and authorization.
The decision_id returned here is REQUIRED to proceed with execution.
This enforces the mandatory approval gate.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class DecisionLogEntry(BaseModel):
    """An immutable decision log entry."""
    decision_id: str = Field(description="Unique decision identifier")
    opportunity_id: str = Field(description="Arbitrage opportunity ID")
    decision: str = Field(description="APPROVE or REJECT")
    reasoning: str = Field(description="Full reasoning for the decision")
    confidence: float = Field(description="Agent confidence in decision")
    expected_profit: float = Field(description="Expected profit if approved")
    risk_factors: List[str] = Field(default_factory=list, description="Identified risks")
    timestamp: int = Field(description="Unix timestamp of decision")
    approved_by: str = Field(default="Flashix", description="Decision maker")


class LogExecutionDecisionResult(BaseModel):
    """Result of logging a decision."""
    success: bool = Field(description="Whether logging succeeded")
    decision_id: str = Field(description="Unique decision ID for this decision")
    logged_at: int = Field(description="Unix timestamp when logged")
    filepath: str = Field(description="Path to decision log file")
    message: str = Field(description="Human-readable confirmation message")


class LogExecutionDecision(BaseTool):
    """
    Logs an execution decision immutably to data/agent_decisions.jsonl.
    
    This is the mandatory final step before execution authorization.
    Returning a valid decision_id proves the approval gate was followed.
    
    Returns decision_id that MUST be included in execution calls as proof.
    """
    
    name: str = "LogExecutionDecision"
    description: str = (
        "Log an execution decision immutably for audit. Records the decision "
        "(APPROVE/REJECT), full reasoning, and risk assessment. "
        "Returns a decision_id that MUST be provided to the execution engine. "
        "This enforces the approval gate: no decision_id = no execution."
    )
    
    def __init__(self):
        super().__init__()
        self.log_dir = "data"
        self.log_file = os.path.join(self.log_dir, "agent_decisions.jsonl")
        # Create log directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _run(
        self,
        opportunity_id: str,
        decision: str,
        reasoning: str,
        confidence: float = 0.0,
        expected_profit: float = 0.0,
        risk_factors: List[str] = None,
        **kwargs
    ) -> str:
        """
        Log an execution decision.
        
        Args:
            opportunity_id: Unique opportunity ID
            decision: "APPROVE" or "REJECT"
            reasoning: Full reasoning for the decision
            confidence: Agent confidence (0.0-1.0)
            expected_profit: Expected profit in USDC
            risk_factors: List of identified risk factors
        
        Returns:
            JSON string of LogExecutionDecisionResult
        """
        if risk_factors is None:
            risk_factors = []
        
        # Validate decision
        decision = decision.upper()
        if decision not in ("APPROVE", "REJECT"):
            result = LogExecutionDecisionResult(
                success=False,
                decision_id="",
                logged_at=0,
                filepath=self.log_file,
                message=f"Invalid decision '{decision}'. Must be 'APPROVE' or 'REJECT'."
            )
            return json.dumps(result.dict())
        
        # Generate unique decision ID
        decision_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # Create log entry
        entry = DecisionLogEntry(
            decision_id=decision_id,
            opportunity_id=opportunity_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            expected_profit=expected_profit,
            risk_factors=risk_factors,
            timestamp=timestamp,
            approved_by="Flashix",
        )
        
        # Write immutably to JSONL file
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry.dict()) + "\n")
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            message = (
                f"✓ Decision logged with ID: {decision_id}. "
                f"Decision: {decision} | Reasoning: {reasoning[:50]}..."
            )
            
            result = LogExecutionDecisionResult(
                success=True,
                decision_id=decision_id,
                logged_at=timestamp,
                filepath=self.log_file,
                message=message,
            )
        except Exception as e:
            result = LogExecutionDecisionResult(
                success=False,
                decision_id="",
                logged_at=0,
                filepath=self.log_file,
                message=f"Failed to log decision: {e}",
            )
        
        return json.dumps(result.dict())
    
    async def _arun(
        self,
        opportunity_id: str,
        decision: str,
        reasoning: str,
        **kwargs
    ) -> str:
        """Async implementation (not used in this context)."""
        return self._run(opportunity_id, decision, reasoning, **kwargs)
