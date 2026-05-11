"""
Atomic flashloan-to-settlement execution engine.
Orchestrates the full arbitrage cycle as a single atomic transaction on 0G Chain:
(1) Borrow: LendingPool.flashLoan()
(2) Arbitrage: ArbitrageExecutor.executeArbitrage() with DEX routing
(3) Close: Automatically close both positions in same tx
(4) Settle & Repay: Calculate P&L, extract profit, repay principal + fees

This is the master orchestration module. All safety checks are hardcoded invariants
that cannot be accidentally misconfigured and must be changed only via deliberate code commit.
"""

import time
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Literal, Dict, Any
import threading
import json
import sqlite3
from datetime import datetime

from compute.arbitrage_analyzer import InferenceOutput

_logger = logging.getLogger(__name__)

# ============================================================================
# HARDCODED SAFETY INVARIANTS (Never read from environment)
# These are the absolute constraints that govern every execution.
# ============================================================================

MIN_COLLATERAL_RATIO = Decimal("1.5")
"""Collateral must stay ≥1.5x during execution. Hard floor to prevent liquidation."""

MAX_POSITION_HOLD_SECONDS = 30
"""Positions must close within 30 seconds of opening. Prevents lingering exposure."""

SIMULATION_REQUIRED = True
"""Every transaction must be simulated before broadcast. Never overridable."""

MAX_GAS_UNITS = 300_000
"""Hard cap on gas units to prevent runaway gas costs."""

PROFIT_VALIDATION_TOLERANCE = Decimal("0.95")
"""Realized profit must be ≥95% of expected to accept settlement."""

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
"""Null address constant for validation checks."""

USDC_DECIMALS = 6
"""USDC uses 6 decimal places on all chains."""

USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
"""Ethereum mainnet USDC contract address."""

CHAIN_ID = 1
"""0G Chain ID (mainnet)."""

FLASHLOAN_FEE_BPS = 5
"""Flashloan fee in basis points (0.05%)."""

# ============================================================================
# EXECUTION DATA STRUCTURES
# Every field is typed and validated before use.
# ============================================================================


@dataclass(frozen=True)
class ExecutionRequest:
    """
    Complete request for atomic arbitrage execution.
    This is the contract between the agent and the execution engine.
    
    Fields are frozen to prevent accidental mutation in a multi-threaded environment.
    """
    opportunity_id: str
    """Unique opportunity identifier, links to reasoning trace."""
    
    decision_id: str
    """Decision log ID. Must match a valid LogExecutionDecision APPROVE record."""
    
    trace_id: str
    """Reasoning trace ID for full auditability."""
    
    signal: InferenceOutput
    """TEE-signed inference signal with expected profit and deadline."""
    
    primary_dex_router: str
    """EVM address of primary DEX (long position)."""
    
    counter_dex_router: str
    """EVM address of counter DEX (short position)."""
    
    borrow_token: str = USDC_ADDRESS
    """Token to borrow. Defaults to USDC."""
    
    borrow_amount_usdc: Decimal = Decimal("0")
    """Amount to borrow in USDC."""
    
    collateral_amount_usdc: Decimal = Decimal("0")
    """Collateral amount in USDC. Must be ≥ borrow_amount * MIN_COLLATERAL_RATIO."""
    
    min_profit_usdc: Decimal = Decimal("0")
    """Minimum acceptable profit (10% below expected to absorb slippage)."""
    
    deadline: int = 0
    """Unix timestamp. Must be signal.expiry_timestamp."""
    
    max_gas_price_gwei: float = 100.0
    """Hard cap on maxFeePerGas to prevent execution during gas spikes."""
    
    simulation_required: bool = True
    """Must be True in production. Never override."""
    
    def __post_init__(self):
        """Validate invariants."""
        if self.signal.expiry_timestamp != self.deadline:
            raise ValueError("deadline must match signal.expiry_timestamp")
        if self.simulation_required is not True:
            raise ValueError("simulation_required must be True")
        if self.borrow_token == ZERO_ADDRESS:
            raise ValueError("borrow_token cannot be the zero address")
        if self.primary_dex_router == ZERO_ADDRESS or self.counter_dex_router == ZERO_ADDRESS:
            raise ValueError("DEX router addresses cannot be the zero address")
        if self.max_gas_price_gwei <= 0:
            raise ValueError("max_gas_price_gwei must be positive")
        if self.borrow_amount_usdc <= 0 or self.min_profit_usdc <= 0:
            raise ValueError("borrow_amount_usdc and min_profit_usdc must be positive")
        if self.collateral_amount_usdc < self.borrow_amount_usdc * MIN_COLLATERAL_RATIO:
            raise ValueError(
                f"Collateral {self.collateral_amount_usdc} < "
                f"Minimum {self.borrow_amount_usdc * MIN_COLLATERAL_RATIO}"
            )
        if self.deadline <= int(time.time()):
            raise ValueError("Deadline is in the past")
        if not self.decision_id:
            raise ValueError("decision_id is required (approval gate)")


@dataclass
class ExecutionResult:
    """
    Complete outcome of an execution attempt.
    Always returned, whether the execution succeeds or fails.
    """
    opportunity_id: str
    decision_id: str
    
    status: Literal[
        "SIMULATED_SUCCESS",
        "SIMULATED_FAILURE",
        "BROADCAST_SUCCESS",
        "BROADCAST_FAILURE",
        "CONFIRMED",
        "REVERTED",
    ]
    """Status of execution. See lifecycle in execute() docstring."""
    
    tx_hash: Optional[str] = None
    """Transaction hash if broadcast succeeded."""
    
    block_number: Optional[int] = None
    """Block number where transaction was mined."""
    
    gas_used: Optional[int] = None
    """Actual gas consumed by confirmed transaction."""
    
    realized_profit_usdc: Optional[Decimal] = None
    """Profit extracted from confirmed transaction's ArbitrageExecuted event."""
    
    execution_latency_ms: float = 0.0
    """Total time from request to final status (broadcast, confirm, or failure)."""
    
    simulation_latency_ms: float = 0.0
    """Time spent in simulation (eth_call)."""
    
    revert_reason: Optional[str] = None
    """If status is REVERTED or SIMULATED_FAILURE, the decoded revert reason."""
    
    explorer_link: Optional[str] = None
    """0G Explorer link to confirmed transaction."""
    
    created_at: int = field(default_factory=lambda: int(time.time()))
    """Unix timestamp when result was created."""


@dataclass
class ApprovalValidation:
    """Result of approval gate validation check."""
    passed: bool
    decision_record: Optional[Dict[str, Any]] = None
    seconds_to_expiry: int = 0
    validated_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class SimulationResult:
    """Result of pre-broadcast eth_call simulation."""
    passed: bool
    simulated_profit_usdc: Decimal = Decimal("0")
    revert_reason: Optional[str] = None
    simulated_at_block: int = 0
    latency_ms: float = 0.0


@dataclass
class GasFees:
    """Current gas fee structure from fee_history."""
    base_fee_gwei: float
    priority_fee_p25_gwei: float
    priority_fee_p50_gwei: float
    max_fee_gwei: float
    estimated_cost_usdc: float
    spike_detected: bool
    spike_severity: Literal["NONE", "MODERATE", "SEVERE"]


@dataclass
class ViabilityCheck:
    """Result of gas viability check."""
    viable: bool
    reason: str
    gas_cost_usdc: float = 0.0
    profit_after_gas: Decimal = Decimal("0")
    margin_pct: float = 0.0


@dataclass
class BroadcastResult:
    """Result of transaction broadcast and confirmation polling."""
    status: Literal["BROADCAST_SUCCESS", "BROADCAST_FAILURE", "CONFIRMED", "REVERTED"]
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    realized_profit_usdc: Optional[Decimal] = None
    explorer_link: Optional[str] = None
    revert_reason: Optional[str] = None
    receipt: Optional[Dict[str, Any]] = None


@dataclass
class SettlementValidation:
    """Result of settlement validation from receipt logs."""
    valid: bool
    reason: str
    realized_profit_usdc: Optional[Decimal] = None
    profit_after_gas: Optional[Decimal] = None
    signal_id_match: bool = True


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================


class ExecutionError(Exception):
    """Base class for all execution errors."""
    pass


class ApprovalGateError(ExecutionError):
    """Approval gate validation failed."""
    pass


class MissingApprovalGate(ApprovalGateError):
    """Decision log record not found."""
    def __init__(self, opportunity_id: str):
        super().__init__(
            f"No approval gate for opportunity {opportunity_id}. "
            "Mandatory decision log check failed."
        )


class RejectedByReasoningEngine(ApprovalGateError):
    """Decision was REJECT, not APPROVE."""
    def __init__(self, decision_id: str, rejection_reason: str):
        super().__init__(
            f"Decision {decision_id} was REJECTED: {rejection_reason}"
        )


class StaleDecision(ApprovalGateError):
    """Decision is older than 25 seconds."""
    def __init__(self, decision_id: str, age_seconds: int):
        super().__init__(
            f"Decision {decision_id} is {age_seconds}s old (max 25s)"
        )


class TransactionBuildError(ExecutionError):
    """Transaction construction failed."""
    pass


class SimulationFailedError(ExecutionError):
    """Pre-broadcast simulation failed."""
    pass


class GasSpikeDetected(ExecutionError):
    """Gas spike prevents execution."""
    pass


class BroadcastError(ExecutionError):
    """Transaction broadcast failed."""
    pass


class SettlementError(ExecutionError):
    """Settlement validation failed."""
    pass


# ============================================================================
# EXECUTION ENGINE MASTER CLASS
# ============================================================================


class ExecutionEngine:
    """
    Master orchestrator for atomic flashloan execution.
    
    Implements the complete cycle:
    1. ApprovalGate.validate() - Verify decision log approval
    2. GasMonitor.is_execution_viable() - Check gas conditions
    3. TransactionBuilder.build_flashloan_tx() - Construct calldata
    4. TransactionSimulator.simulate() - Dry-run with eth_call
    5. Re-check signal expiry after simulation
    6. TransactionBroadcaster.broadcast() - Submit to mempool
    7. SettlementValidator.validate_settlement() - Parse receipt, extract P&L
    8. Return ExecutionResult with final status
    
    Every step is a potential failure point. All failures are logged and result
    in a structured ExecutionResult with full context.
    """
    
    def __init__(self, web3=None, private_key: str = "", db_path: str = "opportunities.db"):
        """
        Initialize the execution engine.
        
        Args:
            web3: web3.py Web3 instance connected to 0G Chain.
            private_key: Private key for transaction signing.
            db_path: Path to SQLite opportunities database.
        """
        self.web3 = web3
        self.private_key = private_key
        self.db_path = db_path
        self.db_lock = threading.Lock()
        
        # Import execution components (submodules built in 9.2-9.7)
        try:
            from agent.execution.approval_gate import ApprovalGate
            from agent.execution.gas_monitor import GasMonitor
            from agent.execution.tx_builder import TransactionBuilder
            from agent.execution.simulator import TransactionSimulator
            from agent.execution.broadcaster import TransactionBroadcaster
            from agent.execution.settlement_validator import SettlementValidator
            
            self.approval_gate = ApprovalGate()
            self.gas_monitor = GasMonitor(web3=self.web3)
            self.tx_builder = TransactionBuilder(web3=self.web3)
            self.simulator = TransactionSimulator(web3=self.web3)
            self.broadcaster = TransactionBroadcaster(web3=self.web3)
            self.settlement_validator = SettlementValidator(web3=self.web3)
        except ImportError as e:
            _logger.warning(f"Execution components not yet initialized: {e}")
    
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute an atomic arbitrage cycle from signal to settlement.
        
        EXECUTION LIFECYCLE (with timing at each step):
        1. ApprovalGate.validate(request) - Hard stop if fails
           → Log EXECUTION_BLOCKED_BY_GATE
        2. GasMonitor.is_execution_viable(request.signal.expected_profit_usdc) - Hard stop if not viable
           → Log EXECUTION_BLOCKED_BY_GAS
        3. TransactionBuilder.build_flashloan_tx(request, wallet_address) - Hard stop if build fails
           → Log TX_BUILD_FAILED
        4. TransactionSimulator.simulate(tx) - Hard stop if simulation fails
           → Log SIMULATION_FAILED with revert reason
        5. Re-check signal expiry (request.deadline > int(time.time()) + 5)
           → Abort if expired to avoid DeadlineExpired revert
        6. TransactionBroadcaster.broadcast(tx, private_key, request)
           → If network exception, log BROADCAST_NETWORK_ERROR, return BROADCAST_FAILURE
           → Do NOT retry (tx may be in mempool despite timeout)
        7. SettlementValidator.validate_settlement(receipt, request)
           → Log outcome and update database
        8. Build and return final ExecutionResult
        
        Args:
            request: ExecutionRequest with all required fields.
        
        Returns:
            ExecutionResult with status and full context.
        """
        start_time = time.perf_counter()
        
        _logger.info(
            f"EXECUTION_START: opportunity_id={request.opportunity_id}, "
            f"decision_id={request.decision_id}, trace_id={request.trace_id}"
        )
        
        try:
            # ================================================================
            # STEP 1: Approval Gate Validation
            # ================================================================
            try:
                approval = self.approval_gate.validate(request)
                if not approval.passed:
                    _logger.critical(
                        f"EXECUTION_BLOCKED_BY_GATE: opportunity_id={request.opportunity_id}, "
                        f"reason={approval.reason if hasattr(approval, 'reason') else 'unknown'}"
                    )
                    return ExecutionResult(
                        opportunity_id=request.opportunity_id,
                        decision_id=request.decision_id,
                        status="BROADCAST_FAILURE",
                        revert_reason="Approval gate validation failed",
                        execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    )
            except ApprovalGateError as e:
                _logger.critical(
                    f"EXECUTION_BLOCKED_BY_GATE: opportunity_id={request.opportunity_id}, "
                    f"error={str(e)}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason=str(e),
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                )
            
            _logger.debug(
                f"APPROVAL_GATE_PASSED: opportunity_id={request.opportunity_id}, "
                f"seconds_to_expiry={approval.seconds_to_expiry}"
            )
            
            # ================================================================
            # STEP 2: Gas Viability Check
            # ================================================================
            try:
                viability = self.gas_monitor.is_execution_viable(
                    request.signal.expected_profit_usdc,
                    request.max_gas_price_gwei,
                )
                if not viability.viable:
                    _logger.critical(
                        f"EXECUTION_BLOCKED_BY_GAS: opportunity_id={request.opportunity_id}, "
                        f"reason={viability.reason}"
                    )
                    return ExecutionResult(
                        opportunity_id=request.opportunity_id,
                        decision_id=request.decision_id,
                        status="BROADCAST_FAILURE",
                        revert_reason=f"Gas check failed: {viability.reason}",
                        execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    )
            except GasSpikeDetected as e:
                _logger.critical(
                    f"EXECUTION_BLOCKED_BY_GAS: opportunity_id={request.opportunity_id}, "
                    f"error={str(e)}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason=str(e),
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                )
            
            _logger.debug(
                f"GAS_CHECK_PASSED: opportunity_id={request.opportunity_id}, "
                f"margin_pct={viability.margin_pct:.2f}%"
            )
            
            # ================================================================
            # STEP 3: Transaction Builder
            # ================================================================
            try:
                # Get wallet address from web3 (derived from private_key)
                from eth_account import Account
                account = Account.from_key(self.private_key)
                wallet_address = account.address
                
                tx = self.tx_builder.build_flashloan_tx(request, wallet_address)
            except TransactionBuildError as e:
                _logger.critical(
                    f"TX_BUILD_FAILED: opportunity_id={request.opportunity_id}, "
                    f"error={str(e)}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason=str(e),
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                )
            
            _logger.debug(
                f"TX_BUILD_SUCCESS: opportunity_id={request.opportunity_id}, "
                f"gas={tx.get('gas', 'unknown')}"
            )
            
            # ================================================================
            # STEP 4: Pre-Broadcast Simulation
            # ================================================================
            try:
                sim_result = self.simulator.simulate(tx, request)
                if not sim_result.passed:
                    _logger.critical(
                        f"SIMULATION_FAILED: opportunity_id={request.opportunity_id}, "
                        f"revert_reason={sim_result.revert_reason}"
                    )
                    return ExecutionResult(
                        opportunity_id=request.opportunity_id,
                        decision_id=request.decision_id,
                        status="SIMULATED_FAILURE",
                        revert_reason=sim_result.revert_reason,
                        execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                        simulation_latency_ms=sim_result.latency_ms,
                    )
            except SimulationFailedError as e:
                _logger.critical(
                    f"SIMULATION_FAILED: opportunity_id={request.opportunity_id}, "
                    f"error={str(e)}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="SIMULATED_FAILURE",
                    revert_reason=str(e),
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    simulation_latency_ms=0.0,
                )
            
            _logger.debug(
                f"SIMULATION_SUCCESS: opportunity_id={request.opportunity_id}, "
                f"simulated_profit_usdc={sim_result.simulated_profit_usdc}, "
                f"latency_ms={sim_result.latency_ms:.2f}"
            )
            
            # ================================================================
            # STEP 5: Re-Check Signal Expiry After Simulation
            # ================================================================
            now = int(time.time())
            time_remaining = request.deadline - now
            if time_remaining < 5:  # Require at least 5 seconds remaining
                _logger.critical(
                    f"SIGNAL_EXPIRED: opportunity_id={request.opportunity_id}, "
                    f"time_remaining={time_remaining}s (min 5s)"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason="Signal deadline expired after simulation",
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    simulation_latency_ms=sim_result.latency_ms,
                )
            
            _logger.debug(
                f"EXPIRY_CHECK_PASSED: opportunity_id={request.opportunity_id}, "
                f"time_remaining={time_remaining}s"
            )
            
            # ================================================================
            # STEP 6: Transaction Broadcast
            # ================================================================
            try:
                broadcast_result = self.broadcaster.broadcast(
                    tx, self.private_key, request
                )
            except BroadcastError as e:
                _logger.critical(
                    f"BROADCAST_NETWORK_ERROR: opportunity_id={request.opportunity_id}, "
                    f"error={str(e)}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason=str(e),
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    simulation_latency_ms=sim_result.latency_ms,
                )
            
            if broadcast_result.status == "BROADCAST_FAILURE":
                _logger.critical(
                    f"TX_BROADCAST_FAILED: opportunity_id={request.opportunity_id}, "
                    f"reason={broadcast_result.revert_reason}"
                )
                return ExecutionResult(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    status="BROADCAST_FAILURE",
                    revert_reason=broadcast_result.revert_reason,
                    execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                    simulation_latency_ms=sim_result.latency_ms,
                )
            
            _logger.info(
                f"TX_BROADCAST_SUCCESS: opportunity_id={request.opportunity_id}, "
                f"tx_hash={broadcast_result.tx_hash}"
            )
            
            # ================================================================
            # STEP 7: Settlement Validation
            # ================================================================
            if broadcast_result.status == "CONFIRMED":
                try:
                    receipt = broadcast_result.receipt or {}
                    settlement = self.settlement_validator.validate_settlement(receipt, request)
                    if not settlement.valid:
                        _logger.warning(
                            f"SETTLEMENT_INVALID: opportunity_id={request.opportunity_id}, "
                            f"reason={settlement.reason}"
                        )
                except SettlementError as e:
                    _logger.critical(
                        f"SETTLEMENT_ERROR: opportunity_id={request.opportunity_id}, "
                        f"error={str(e)}"
                    )
            
            _logger.info(
                f"EXECUTION_COMPLETE: opportunity_id={request.opportunity_id}, "
                f"status={broadcast_result.status}, "
                f"tx_hash={broadcast_result.tx_hash}"
            )
            
            # ================================================================
            # STEP 8: Build Final ExecutionResult
            # ================================================================
            result = ExecutionResult(
                opportunity_id=request.opportunity_id,
                decision_id=request.decision_id,
                status=broadcast_result.status,  # type: ignore
                tx_hash=broadcast_result.tx_hash,
                block_number=broadcast_result.block_number,
                gas_used=broadcast_result.gas_used,
                realized_profit_usdc=broadcast_result.realized_profit_usdc,
                execution_latency_ms=(time.perf_counter() - start_time) * 1000,
                simulation_latency_ms=sim_result.latency_ms,
                revert_reason=broadcast_result.revert_reason,
                explorer_link=broadcast_result.explorer_link,
            )
            
            return result
        
        except Exception as e:
            _logger.critical(
                f"UNEXPECTED_EXECUTION_ERROR: opportunity_id={request.opportunity_id}, "
                f"error={str(e)}", exc_info=True
            )
            return ExecutionResult(
                opportunity_id=request.opportunity_id,
                decision_id=request.decision_id,
                status="BROADCAST_FAILURE",
                revert_reason=str(e),
                execution_latency_ms=(time.perf_counter() - start_time) * 1000,
            )
    
    def _init_db(self) -> None:
        """Initialize opportunities database if it doesn't exist."""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    realized_profit_usdc REAL,
                    gas_used INTEGER,
                    execution_latency_ms REAL,
                    tx_hash TEXT,
                    explorer_link TEXT,
                    created_at INTEGER,
                    updated_at INTEGER
                )
            """)
            
            conn.commit()
            conn.close()
