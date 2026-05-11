"""
Approval gate validator.
Absolute first check in the execution pipeline - no tx construction, simulation, 
or gas estimation happens until this gate passes.

Enforces the mandatory decision log check before any transaction is constructed.
"""

import time
import json
import logging
import os
from typing import Optional, Dict, Any

from agent.execution_engine import (
    ExecutionRequest,
    ApprovalValidation,
    ApprovalGateError,
    MissingApprovalGate,
    RejectedByReasoningEngine,
    StaleDecision,
)

_logger = logging.getLogger(__name__)

# Path to decision log file
DECISION_LOG_PATH = "data/agent_decisions.jsonl"


class ApprovalGate:
    """
    Validates that an execution request has a valid approval from the reasoning engine.
    
    This is the absolute first check in the execution pipeline. Four sequential checks:
    1. Decision Log Existence - Does a record exist for this decision_id?
    2. Decision Value - Is the decision APPROVE (not REJECT)?
    3. Decision Freshness - Is the decision fresh enough (< 25 seconds old)?
    4. Signal Expiry - Is there enough time remaining (≥ 8 seconds)?
    """
    
    def __init__(self, log_path: str = DECISION_LOG_PATH):
        """
        Initialize the approval gate.
        
        Args:
            log_path: Path to the decision log JSONL file.
        """
        self.log_path = log_path
    
    def validate(self, request: ExecutionRequest) -> ApprovalValidation:
        """
        Perform four sequential approval checks on the execution request.
        
        Raises:
            MissingApprovalGate: Decision log record not found
            RejectedByReasoningEngine: Decision was REJECT
            StaleDecision: Decision is too old (> 25 seconds)
        
        Args:
            request: ExecutionRequest to validate
        
        Returns:
            ApprovalValidation with passed=True and decision_record if all checks pass
        """
        
        _logger.debug(
            f"APPROVAL_GATE_CHECK_START: opportunity_id={request.opportunity_id}, "
            f"decision_id={request.decision_id}"
        )
        
        # ================================================================
        # CHECK 1: Decision Log Existence
        # ================================================================
        decision_record = self._find_decision_record(request.decision_id, request.opportunity_id)
        
        if decision_record is None:
            _logger.critical(
                f"APPROVAL_GATE_CHECK_FAILED: opportunity_id={request.opportunity_id}, "
                f"decision_id={request.decision_id}, reason=MISSING_DECISION_LOG"
            )
            raise MissingApprovalGate(request.opportunity_id)
        
        _logger.debug(
            f"DECISION_LOG_FOUND: opportunity_id={request.opportunity_id}, "
            f"decision_id={request.decision_id}"
        )
        
        # ================================================================
        # CHECK 2: Decision Value
        # ================================================================
        decision_value = decision_record.get("decision", "").upper()
        
        if decision_value != "APPROVE":
            rejection_reason = decision_record.get(
                "rejection_reason",
                decision_record.get("reasoning", "Unknown reason")
            )
            _logger.critical(
                f"APPROVAL_GATE_CHECK_FAILED: opportunity_id={request.opportunity_id}, "
                f"decision_id={request.decision_id}, reason=DECISION_REJECTED, "
                f"rejection_reason={rejection_reason}"
            )
            raise RejectedByReasoningEngine(request.decision_id, rejection_reason)
        
        _logger.debug(
            f"DECISION_VALUE_APPROVED: opportunity_id={request.opportunity_id}, "
            f"decision_id={request.decision_id}"
        )
        
        # ================================================================
        # CHECK 3: Decision Freshness
        # ================================================================
        decision_timestamp = decision_record.get("timestamp", decision_record.get("created_at", 0))
        current_time = int(time.time())
        decision_age_seconds = current_time - decision_timestamp
        
        if decision_age_seconds >= 25:
            _logger.critical(
                f"APPROVAL_GATE_CHECK_FAILED: opportunity_id={request.opportunity_id}, "
                f"decision_id={request.decision_id}, reason=STALE_DECISION, "
                f"age_seconds={decision_age_seconds}"
            )
            raise StaleDecision(request.decision_id, decision_age_seconds)
        
        _logger.debug(
            f"DECISION_FRESHNESS_OK: opportunity_id={request.opportunity_id}, "
            f"decision_age_seconds={decision_age_seconds}"
        )
        
        # ================================================================
        # CHECK 4: Signal Expiry (require ≥ 8 seconds remaining)
        # ================================================================
        time_remaining = request.deadline - current_time
        
        if time_remaining < 8:
            _logger.critical(
                f"APPROVAL_GATE_CHECK_FAILED: opportunity_id={request.opportunity_id}, "
                f"decision_id={request.decision_id}, reason=INSUFFICIENT_TIME_REMAINING, "
                f"time_remaining={time_remaining}s (min 8s)"
            )
            raise ApprovalGateError(
                f"Signal deadline too close for opportunity {request.opportunity_id}: {time_remaining}s remaining"
            )
        
        _logger.debug(
            f"SIGNAL_EXPIRY_OK: opportunity_id={request.opportunity_id}, "
            f"time_remaining={time_remaining}s"
        )
        
        # ================================================================
        # ALL CHECKS PASSED
        # ================================================================
        result = ApprovalValidation(
            passed=True,
            decision_record=decision_record,
            seconds_to_expiry=time_remaining,
            validated_at=current_time,
        )
        
        _logger.debug(
            f"APPROVAL_GATE_PASSED: opportunity_id={request.opportunity_id}, "
            f"decision_id={request.decision_id}, "
            f"seconds_to_expiry={time_remaining}"
        )
        
        return result
    
    def _find_decision_record(
        self, decision_id: str, opportunity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a decision record in the log file by decision_id and opportunity_id.
        
        Args:
            decision_id: Decision ID to search for
            opportunity_id: Opportunity ID to cross-check
        
        Returns:
            Decision record dict if found, None otherwise
        """
        
        if not os.path.exists(self.log_path):
            _logger.warning(f"Decision log file not found: {self.log_path}")
            return None
        
        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        _logger.warning(f"Skipping malformed line in decision log: {line[:100]}")
                        continue
                    
                    # Match both decision_id and opportunity_id for safety
                    if (record.get("decision_id") == decision_id and
                        record.get("opportunity_id") == opportunity_id):
                        if "rejection_reason" not in record and "reasoning" in record:
                            record["rejection_reason"] = record.get("reasoning", "")
                        return record
        
        except IOError as e:
            _logger.error(f"Error reading decision log: {e}")
            return None
        
        return None
