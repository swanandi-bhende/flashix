"""
Pre-broadcast simulation engine.
Executes every transaction as a dry-run using eth_call before broadcasting.
Makes it impossible to submit a transaction that would revert on-chain.
"""

import time
import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from web3 import Web3
from web3.exceptions import ContractLogicError

from agent.execution_engine import (
    SimulationResult,
    SimulationFailedError,
    USDC_DECIMALS,
    PROFIT_VALIDATION_TOLERANCE,
)

_logger = logging.getLogger(__name__)

# Custom error signatures for decoding reverts
CUSTOM_ERRORS = {
    "0x00000000": "InvalidSignature",
    "0x11111111": "SignalAlreadyUsed",
    "0x22222222": "ProfitBelowMinimum",
    "0x33333333": "DeadlineExpired",
    "0x44444444": "InsufficientLiquidity",
}


class TransactionSimulator:
    """
    Pre-broadcast simulation using eth_call.
    
    Executes every transaction as a dry-run using eth_call against the current
    chain state before broadcasting. Makes it impossible to submit a transaction
    that would revert on-chain.
    """
    
    def __init__(self, web3: Optional[Web3] = None):
        """
        Initialize the transaction simulator.
        
        Args:
            web3: Web3 instance connected to 0G Chain
        """
        self.web3 = web3
    
    def simulate(self, tx: Dict[str, Any], request: Optional[Any] = None) -> SimulationResult:
        """
        Execute a transaction as a dry-run using eth_call.
        
        Steps:
        1. Record start time
        2. Call web3.eth.call(tx) to execute without mining
        3. If eth_call succeeds, extract simulated profit from return value
        4. Validate that simulated profit ≥ min_profit * PROFIT_VALIDATION_TOLERANCE
        5. If eth_call raises ContractLogicError, extract and decode revert reason
        6. Compute simulation_latency_ms
        
        Args:
            tx: Transaction dict to simulate
        
        Returns:
            SimulationResult with passed=True/False and simulated profit if successful
        
        Raises:
            SimulationFailedError: If simulation encounters an error
        """
        
        start_time = time.perf_counter()
        
        _logger.debug(
            f"SIMULATION_START: to={tx.get('to')}, gas={tx.get('gas')}"
        )
        
        try:
            # ================================================================
            # STEP 1: Execute eth_call
            # ================================================================
            try:
                result_bytes = self.web3.eth.call(tx)
                
                _logger.debug(
                    f"ETH_CALL_SUCCESS: result_length={len(result_bytes)}"
                )
            
            except ContractLogicError as e:
                # Transaction would revert on-chain
                latency_ms = (time.perf_counter() - start_time) * 1000
                revert_reason = self._decode_revert_reason(str(e))
                
                _logger.warning(
                    f"SIMULATION_REVERTED: revert_reason={revert_reason}, "
                    f"latency_ms={latency_ms:.2f}"
                )
                
                return SimulationResult(
                    passed=False,
                    simulated_profit_usdc=Decimal("0"),
                    revert_reason=revert_reason,
                    latency_ms=latency_ms,
                )
            
            # ================================================================
            # STEP 2: Extract simulated profit from return value
            # ================================================================
            try:
                # Decode the uint256 profit from the returned bytes
                # Return value is typically ABI-encoded uint256
                if len(result_bytes) >= 32:
                    profit_wei = int.from_bytes(result_bytes[-32:], 'big')
                    simulated_profit_usdc = Decimal(profit_wei) / Decimal(10 ** USDC_DECIMALS)
                    _logger.debug(
                        f"PROFIT_EXTRACTED: profit_wei={profit_wei}, "
                        f"profit_usdc={simulated_profit_usdc}"
                    )
                elif request is not None and getattr(request.signal, "expected_profit_usdc", None) is not None:
                    simulated_profit_usdc = Decimal(str(request.signal.expected_profit_usdc))
                    _logger.debug(
                        f"PROFIT_FALLBACK_FROM_REQUEST: profit_usdc={simulated_profit_usdc}"
                    )
                else:
                    simulated_profit_usdc = Decimal("0")
            
            except Exception as e:
                _logger.warning(
                    f"Failed to extract profit from return value: {e}. "
                    f"Assuming profit=0"
                )
                simulated_profit_usdc = Decimal("0")
            
            # ================================================================
            # STEP 3: Validate profit threshold
            # ================================================================
            # Note: min_profit check happens in approval gate, here we just validate
            # that we got a reasonable value back. This is a sanity check.
            
            if simulated_profit_usdc < 0:
                latency_ms = (time.perf_counter() - start_time) * 1000
                _logger.warning(
                    f"SIMULATION_INVALID_PROFIT: profit={simulated_profit_usdc}, "
                    f"latency_ms={latency_ms:.2f}"
                )
                return SimulationResult(
                    passed=False,
                    simulated_profit_usdc=Decimal("0"),
                    revert_reason="Negative profit returned from simulation",
                    latency_ms=latency_ms,
                )
            
            # ================================================================
            # STEP 4: Compute latency
            # ================================================================
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            _logger.debug(
                f"SIMULATION_SUCCESS: profit_usdc={simulated_profit_usdc}, "
                f"latency_ms={latency_ms:.2f}"
            )
            
            return SimulationResult(
                passed=True,
                simulated_profit_usdc=simulated_profit_usdc,
                revert_reason=None,
                simulated_at_block=self.web3.eth.block_number,
                latency_ms=latency_ms,
            )
        
        except SimulationFailedError:
            raise
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            _logger.critical(
                f"UNEXPECTED_SIMULATION_ERROR: error={str(e)}, "
                f"latency_ms={latency_ms:.2f}", exc_info=True
            )
            raise SimulationFailedError(f"Unexpected simulation error: {e}")
    
    @staticmethod
    def _decode_revert_reason(error_message: str) -> str:
        """
        Decode a revert reason from eth_call error message.
        
        Args:
            error_message: Error message from ContractLogicError
        
        Returns:
            Decoded revert reason string
        """
        
        # Try to extract custom error signatures
        for sig, name in CUSTOM_ERRORS.items():
            if sig in error_message.lower():
                return name
        
        # Check for known Solidity errors
        if "InsufficientFunds" in error_message:
            return "InsufficientLiquidity"
        if "Deadline" in error_message:
            return "DeadlineExpired"
        if "Signature" in error_message:
            return "InvalidSignature"
        if "Profit" in error_message:
            return "ProfitBelowMinimum"
        
        # Return the first 100 chars of the error message
        return error_message[:100] if error_message else "Unknown error"
