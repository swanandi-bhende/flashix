"""
Decision logger for comprehensive auditability and performance monitoring.
Distinct from the LogExecutionDecision tool; this tracks reasoning traces and metrics.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class DecisionLogger:
    """
    Comprehensive logging of all agent invocations for auditability and monitoring.
    
    Records:
    - Complete reasoning traces
    - Tool call sequences
    - Performance metrics
    - Token usage and costs
    - Consistency scoring
    """
    
    def __init__(self, log_dir: str = "data"):
        """
        Initialize the decision logger.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "agent_decisions.jsonl")
        self.metrics_file = os.path.join(log_dir, "agent_metrics.json")
        
        # Create directories if needed
        os.makedirs(log_dir, exist_ok=True)
    
    def log_agent_invocation(
        self,
        signal: Dict[str, Any],
        agent_response: Dict[str, Any],
        elapsed_ms: float,
        tool_calls: List[str],
        gemini_input_tokens: int = 0,
        gemini_output_tokens: int = 0,
        memory_window_size: int = 0,
    ) -> str:
        """
        Log a complete agent invocation.
        
        Args:
            signal: Original InferenceOutput signal
            agent_response: Agent's response dict
            elapsed_ms: Time taken for reasoning in milliseconds
            tool_calls: List of tool names called in order
            gemini_input_tokens: Input tokens sent to Gemini
            gemini_output_tokens: Output tokens from Gemini
            memory_window_size: Size of memory window used
        
        Returns:
            Invocation ID for reference
        """
        import uuid
        import time
        
        invocation_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # Estimate cost (Gemini Flash pricing as of May 2026)
        input_cost_per_1m = 0.075  # $0.075 per 1M input tokens
        output_cost_per_1m = 0.30  # $0.30 per 1M output tokens
        gemini_cost_usd = (
            (gemini_input_tokens / 1_000_000) * input_cost_per_1m +
            (gemini_output_tokens / 1_000_000) * output_cost_per_1m
        )
        
        record = {
            "invocation_id": invocation_id,
            "timestamp": timestamp,
            "opportunity_id": signal.get("opportunity_id", "unknown"),
            "signal_confidence": signal.get("confidence", 0.0),
            "signal_expected_profit": signal.get("expected_profit_usdc", 0.0),
            "decision": agent_response.get("decision", "REJECT"),
            "decision_id": agent_response.get("decision_id", ""),
            "reasoning_summary": agent_response.get("reasoning_summary", ""),
            "tool_calls_sequence": tool_calls,
            "tool_call_count": len(tool_calls),
            "total_elapsed_ms": elapsed_ms,
            "gemini_input_tokens": gemini_input_tokens,
            "gemini_output_tokens": gemini_output_tokens,
            "gemini_cost_usd_estimate": round(gemini_cost_usd, 6),
            "memory_window_size": memory_window_size,
            "model_version": signal.get("model_version", "unknown"),
        }
        
        # Append to log file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
        
        return invocation_id
    
    def compute_reasoning_consistency_score(self, last_n: int = 50) -> float:
        """
        Compute reasoning consistency score.
        
        Loads the last N decisions, groups by scenario type, and measures
        what percentage of identical scenarios received the same decision.
        
        Target: > 95% consistency
        
        Args:
            last_n: Number of recent decisions to analyze
        
        Returns:
            Consistency score 0.0-100.0
        """
        if not os.path.exists(self.log_file):
            return 0.0
        
        # Load recent decisions
        decisions = []
        with open(self.log_file, "r") as f:
            lines = f.readlines()
            for line in lines[-last_n:]:
                try:
                    decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        
        if not decisions:
            return 0.0
        
        # Group by scenario type (inferred from signal parameters)
        scenarios: Dict[str, List[str]] = {}
        
        for decision in decisions:
            # Create scenario key from confidence and profit thresholds
            confidence = decision.get("signal_confidence", 0.0)
            profit = decision.get("signal_expected_profit", 0.0)
            
            # Bucket into scenario categories
            confidence_bucket = f"{int(confidence * 10)}"
            profit_bucket = f"{int(profit)}"
            scenario_key = f"conf_{confidence_bucket}_profit_{profit_bucket}"
            
            if scenario_key not in scenarios:
                scenarios[scenario_key] = []
            
            scenarios[scenario_key].append(decision.get("decision", "REJECT"))
        
        # Calculate consistency
        consistent_scenarios = 0
        for scenario_key, decisions_list in scenarios.items():
            if len(decisions_list) > 1:
                # Check if all decisions in this scenario are the same
                if len(set(decisions_list)) == 1:
                    consistent_scenarios += 1
            else:
                # Single scenario always "consistent"
                consistent_scenarios += 1
        
        consistency_score = (consistent_scenarios / len(scenarios) * 100) if scenarios else 0.0
        return round(consistency_score, 1)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for monitoring.
        
        Returns:
            Dictionary with:
            - total_decisions: Total number of decisions made
            - approve_rate: Percentage of APPROVE decisions
            - avg_reasoning_latency_ms: Average reasoning time
            - p95_reasoning_latency_ms: 95th percentile latency
            - avg_tool_calls_per_decision: Average tools called per decision
            - gemini_total_cost_usd: Total estimated cost
            - consistency_score: Consistency score 0-100
        """
        if not os.path.exists(self.log_file):
            return {
                "total_decisions": 0,
                "approve_rate": 0.0,
                "avg_reasoning_latency_ms": 0.0,
                "p95_reasoning_latency_ms": 0.0,
                "avg_tool_calls_per_decision": 0.0,
                "gemini_total_cost_usd": 0.0,
                "consistency_score": 0.0,
            }
        
        decisions = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        
        if not decisions:
            return {
                "total_decisions": 0,
                "approve_rate": 0.0,
                "avg_reasoning_latency_ms": 0.0,
                "p95_reasoning_latency_ms": 0.0,
                "avg_tool_calls_per_decision": 0.0,
                "gemini_total_cost_usd": 0.0,
                "consistency_score": 0.0,
            }
        
        # Calculate metrics
        approvals = sum(1 for d in decisions if d.get("decision") == "APPROVE")
        approve_rate = (approvals / len(decisions) * 100) if decisions else 0.0
        
        latencies = [d.get("total_elapsed_ms", 0) for d in decisions]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        latencies_sorted = sorted(latencies)
        p95_idx = int(len(latencies_sorted) * 0.95)
        p95_latency = latencies_sorted[p95_idx] if p95_idx < len(latencies_sorted) else 0.0
        
        tool_calls = [d.get("tool_call_count", 0) for d in decisions]
        avg_tools = sum(tool_calls) / len(tool_calls) if tool_calls else 0.0
        
        total_cost = sum(d.get("gemini_cost_usd_estimate", 0.0) for d in decisions)
        
        consistency = self.compute_reasoning_consistency_score()
        
        return {
            "total_decisions": len(decisions),
            "approve_rate": round(approve_rate, 1),
            "avg_reasoning_latency_ms": round(avg_latency, 1),
            "p95_reasoning_latency_ms": round(p95_latency, 1),
            "avg_tool_calls_per_decision": round(avg_tools, 2),
            "gemini_total_cost_usd": round(total_cost, 4),
            "consistency_score": consistency,
        }
