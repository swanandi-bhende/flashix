"""
Atomic flashloan execution module.
Orchestrates the complete arbitrage cycle from decision approval to on-chain settlement.
"""

from agent.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
    ExecutionResult,
    ExecutionError,
    ApprovalGateError,
    MissingApprovalGate,
    RejectedByReasoningEngine,
    StaleDecision,
    TransactionBuildError,
    SimulationFailedError,
    GasSpikeDetected,
    BroadcastError,
    SettlementError,
    ApprovalValidation,
    SimulationResult,
    GasFees,
    ViabilityCheck,
    BroadcastResult,
    SettlementValidation,
    # Safety constants
    MIN_COLLATERAL_RATIO,
    MAX_POSITION_HOLD_SECONDS,
    SIMULATION_REQUIRED,
    MAX_GAS_UNITS,
    PROFIT_VALIDATION_TOLERANCE,
)

__all__ = [
    "ExecutionEngine",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionError",
    "ApprovalGateError",
    "MissingApprovalGate",
    "RejectedByReasoningEngine",
    "StaleDecision",
    "TransactionBuildError",
    "SimulationFailedError",
    "GasSpikeDetected",
    "BroadcastError",
    "SettlementError",
    "ApprovalValidation",
    "SimulationResult",
    "GasFees",
    "ViabilityCheck",
    "BroadcastResult",
    "SettlementValidation",
    "MIN_COLLATERAL_RATIO",
    "MAX_POSITION_HOLD_SECONDS",
    "SIMULATION_REQUIRED",
    "MAX_GAS_UNITS",
    "PROFIT_VALIDATION_TOLERANCE",
]
