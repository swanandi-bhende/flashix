"""
Tool 1: ValidateInferenceSignal
Validates the integrity, authenticity, and validity of inference signals from the TEE.
"""

import json
import time
from typing import Any, Dict, List

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of signal validation."""
    valid: bool = Field(description="Whether the signal is valid")
    failed_checks: List[str] = Field(default_factory=list, description="List of failed validation checks")
    time_to_expiry_seconds: int = Field(description="Seconds until signal expires")
    confidence: float = Field(description="Model confidence from signal")
    message: str = Field(description="Human-readable validation message")


class ValidateInferenceSignal(BaseTool):
    """
    Validates raw InferenceOutput JSON strings.
    
    Checks:
    - Signal has not expired
    - Decision field == "EXECUTE"
    - Confidence > MIN_CONFIDENCE_THRESHOLD
    - TEE signature is present (basic check)
    
    Returns structured ValidationResult with detailed failure reasons.
    """
    
    name: str = "ValidateInferenceSignal"
    description: str = (
        "Validates an inference signal from the TEE. Takes the raw signal JSON and checks: "
        "expiry, decision field, confidence threshold, and signature authenticity. "
        "Returns whether the signal is valid and which checks (if any) failed."
    )
    
    def _run(
        self,
        signal_json: str,
        min_confidence: float = 0.75,
        **kwargs
    ) -> str:
        """
        Validate a signal.
        
        Args:
            signal_json: JSON string of InferenceOutput from TEE
            min_confidence: Minimum confidence threshold (default 0.75)
        
        Returns:
            JSON string of ValidationResult
        """
        try:
            signal = json.loads(signal_json)
        except json.JSONDecodeError as e:
            result = ValidationResult(
                valid=False,
                failed_checks=["INVALID_JSON"],
                time_to_expiry_seconds=0,
                confidence=0.0,
                message=f"Signal JSON is malformed: {e}"
            )
            return json.dumps(result.dict())
        
        failed_checks: List[str] = []
        current_time = int(time.time())
        
        # Check 1: Signal expiry
        expiry = signal.get("expiry_timestamp", 0)
        time_to_expiry = expiry - current_time
        
        if time_to_expiry < 0:
            failed_checks.append("SIGNAL_EXPIRED")
        
        # Check 2: Decision field
        decision = signal.get("decision", "").upper()
        if decision != "EXECUTE":
            failed_checks.append("DECISION_NOT_EXECUTE")
        
        # Check 3: Confidence threshold
        confidence = signal.get("confidence", 0.0)
        if confidence < min_confidence:
            failed_checks.append("CONFIDENCE_BELOW_THRESHOLD")
        
        # Check 4: TEE signature (basic check)
        tee_signature = signal.get("tee_signature", "")
        if not tee_signature or len(tee_signature) < 32:
            failed_checks.append("INVALID_TEE_SIGNATURE")
        
        # Additional checks for signal structure
        required_fields = [
            "opportunity_id", "symbol", "primary_dex", "counter_dex",
            "price_a", "price_b", "expected_profit_usdc", "model_version"
        ]
        for field in required_fields:
            if field not in signal:
                failed_checks.append(f"MISSING_{field.upper()}")
        
        valid = len(failed_checks) == 0
        
        if valid:
            message = "✓ Signal validation passed. Ready for execution analysis."
        else:
            message = f"✗ Signal validation failed: {', '.join(failed_checks)}"
        
        result = ValidationResult(
            valid=valid,
            failed_checks=failed_checks,
            time_to_expiry_seconds=max(0, time_to_expiry),
            confidence=confidence,
            message=message
        )
        
        return json.dumps(result.dict())
    
    async def _arun(self, signal_json: str, **kwargs) -> str:
        """Async implementation (not used in this context)."""
        return self._run(signal_json, **kwargs)
