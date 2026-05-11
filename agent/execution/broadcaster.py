"""
Transaction broadcaster with nonce management and receipt polling.
Handles the final step of submitting a simulation-validated transaction
to the 0G Chain mempool and polling for confirmation.
"""

import time
import logging
import threading
import json
from typing import Optional, Dict, Any
from decimal import Decimal

from web3 import Web3
from eth_account import Account
from web3.exceptions import ContractLogicError

from agent.execution_engine import (
    ExecutionRequest,
    BroadcastResult,
    BroadcastError,
    USDC_DECIMALS,
)

_logger = logging.getLogger(__name__)

# Configuration
CONFIRMATION_POLL_INTERVAL_MS = 500
CONFIRMATION_TIMEOUT_SECONDS = 30
EXPLORER_BASE_URL = "https://chainscan-galileo.0g.ai/tx"
ARBITRAGE_EXECUTOR_ABI_PATH = "contracts/abi/ArbitrageExecutor.json"


class NonceManager:
    """
    Thread-safe nonce cache to prevent nonce collisions.
    """
    
    def __init__(self, web3: Web3):
        """Initialize the nonce manager."""
        self.web3 = web3
        self.nonce_cache: Dict[str, int] = {}
        self.lock = threading.Lock()
    
    def get_next_nonce(self, address: str) -> int:
        """
        Get the next nonce for an address.
        
        On first call, fetches web3.eth.get_transaction_count(address, 'pending').
        On subsequent calls, increments atomically.
        
        Args:
            address: EVM address to get nonce for
        
        Returns:
            Next available nonce
        """
        address = Web3.to_checksum_address(address)
        
        with self.lock:
            if address not in self.nonce_cache:
                # First call: fetch from chain
                nonce = self.web3.eth.get_transaction_count(address, 'pending')
                self.nonce_cache[address] = nonce
                _logger.debug(f"NONCE_INITIALIZED: address={address}, nonce={nonce}")
            else:
                # Subsequent calls: increment
                self.nonce_cache[address] += 1
            
            return self.nonce_cache[address]


class TransactionBroadcaster:
    """
    Broadcasts signed transactions to the mempool and polls for confirmation.
    """
    
    def __init__(self, web3: Optional[Web3] = None):
        """
        Initialize the broadcaster.
        
        Args:
            web3: Web3 instance connected to 0G Chain
        """
        self.web3 = web3
        self.nonce_manager = NonceManager(web3) if web3 else None
        self.arbitrage_executor_contract = self._load_executor_contract() if web3 else None
    
    def broadcast(
        self, tx: Dict[str, Any], private_key: str, request: ExecutionRequest
    ) -> BroadcastResult:
        """
        Sign, broadcast, and poll for confirmation.
        
        Steps:
        1. Sign the transaction with private_key
        2. Submit to mempool via web3.eth.send_raw_transaction()
        3. Log broadcast event
        4. Poll web3.eth.get_transaction_receipt() every 500ms for up to 30 seconds
        5. On confirmed receipt, decode ArbitrageExecuted event from logs
        6. Extract realized profit and compute explorer URL
        7. Return BroadcastResult with full context
        
        If receipt.status == 0 (revert), replay eth_call to extract revert reason.
        
        Args:
            tx: Transaction dict ready for signing
            private_key: Private key to sign with
            request: Original ExecutionRequest for context
        
        Returns:
            BroadcastResult with status and final transaction details
        
        Raises:
            BroadcastError: If broadcast fails (network exception, etc.)
        """
        
        start_time = time.perf_counter()
        
        _logger.debug(
            f"BROADCAST_START: opportunity_id={request.opportunity_id}, "
            f"tx_from={tx.get('from')}"
        )
        
        try:
            # ================================================================
            # STEP 1: Sign transaction
            # ================================================================
            try:
                signed_tx = self.web3.eth.account.sign_transaction(tx, private_key)
                _logger.debug(
                    f"TX_SIGNED: opportunity_id={request.opportunity_id}"
                )
            except Exception as e:
                raise BroadcastError(f"Failed to sign transaction: {e}")
            
            # ================================================================
            # STEP 2: Submit to mempool
            # ================================================================
            try:
                raw_transaction = getattr(signed_tx, "rawTransaction", None) or getattr(signed_tx, "raw_transaction")
                tx_hash = self.web3.eth.send_raw_transaction(raw_transaction)
                tx_hash_hex = tx_hash.hex()
                _logger.info(
                    f"TX_BROADCAST: hash={tx_hash_hex}, "
                    f"opportunity_id={request.opportunity_id}, "
                    f"gas_price={tx.get('maxFeePerGas')}, "
                    f"nonce={tx.get('nonce')}"
                )
            except Exception as e:
                raise BroadcastError(f"Failed to send transaction: {e}")
            
            # ================================================================
            # STEP 3: Wait for confirmation
            # ================================================================
            receipt = self._wait_for_confirmation(tx_hash_hex)
            
            if receipt is None:
                _logger.critical(
                    f"BROADCAST_TIMEOUT: opportunity_id={request.opportunity_id}, "
                    f"tx_hash={tx_hash_hex}, timeout={CONFIRMATION_TIMEOUT_SECONDS}s"
                )
                return BroadcastResult(
                    status="BROADCAST_FAILURE",
                    tx_hash=tx_hash_hex,
                    revert_reason=f"No confirmation within {CONFIRMATION_TIMEOUT_SECONDS}s",
                )
            
            block_number = receipt.get('blockNumber')
            gas_used = receipt.get('gasUsed')
            status = receipt.get('status')
            
            _logger.debug(
                f"TX_CONFIRMED: opportunity_id={request.opportunity_id}, "
                f"block={block_number}, gas_used={gas_used}, status={status}"
            )
            
            # ================================================================
            # STEP 4: Check transaction status
            # ================================================================
            if status == 1:
                # Transaction succeeded
                _logger.info(
                    f"TX_SUCCESS: opportunity_id={request.opportunity_id}, "
                    f"tx_hash={tx_hash_hex}, block={block_number}"
                )
                
                # Extract profit from event logs
                realized_profit_usdc = self._extract_profit_from_logs(receipt)
                
                explorer_link = f"{EXPLORER_BASE_URL}/{tx_hash_hex}"
                
                return BroadcastResult(
                    status="CONFIRMED",
                    tx_hash=tx_hash_hex,
                    block_number=block_number,
                    gas_used=gas_used,
                    realized_profit_usdc=realized_profit_usdc,
                    explorer_link=explorer_link,
                    receipt=receipt,
                )
            
            elif status == 0:
                # Transaction reverted
                _logger.critical(
                    f"TX_REVERTED: opportunity_id={request.opportunity_id}, "
                    f"tx_hash={tx_hash_hex}, block={block_number}"
                )
                
                # Try to extract revert reason by replaying
                revert_reason = self._extract_revert_reason(tx, receipt)
                
                explorer_link = f"{EXPLORER_BASE_URL}/{tx_hash_hex}"
                
                return BroadcastResult(
                    status="REVERTED",
                    tx_hash=tx_hash_hex,
                    block_number=block_number,
                    gas_used=gas_used,
                    revert_reason=revert_reason,
                    explorer_link=explorer_link,
                    receipt=receipt,
                )
            
            else:
                # Status is pending or unknown (shouldn't happen after confirmation)
                _logger.warning(
                    f"TX_UNKNOWN_STATUS: opportunity_id={request.opportunity_id}, "
                    f"status={status}"
                )
                return BroadcastResult(
                    status="BROADCAST_FAILURE",
                    tx_hash=tx_hash_hex,
                    block_number=block_number,
                    revert_reason="Unknown transaction status",
                )
        
        except BroadcastError:
            raise
        except Exception as e:
            _logger.critical(
                f"UNEXPECTED_BROADCAST_ERROR: opportunity_id={request.opportunity_id}, "
                f"error={str(e)}", exc_info=True
            )
            raise BroadcastError(f"Unexpected broadcast error: {e}")
    
    def _wait_for_confirmation(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Poll for transaction receipt until confirmed or timeout.
        
        Args:
            tx_hash: Transaction hash to poll for
        
        Returns:
            Receipt dict if confirmed, None if timeout
        """
        start_time = time.perf_counter()
        poll_interval = CONFIRMATION_POLL_INTERVAL_MS / 1000.0  # Convert to seconds
        
        while True:
            elapsed = time.perf_counter() - start_time
            
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    _logger.debug(
                        f"RECEIPT_FOUND: tx_hash={tx_hash}, "
                        f"confirmation_latency_ms={elapsed * 1000:.0f}"
                    )
                    return receipt
            except Exception as e:
                # Receipt not ready yet
                pass
            
            if elapsed > CONFIRMATION_TIMEOUT_SECONDS:
                return None
            
            time.sleep(poll_interval)
    
    def _extract_profit_from_logs(self, receipt: Dict[str, Any]) -> Optional[Decimal]:
        """
        Extract realized profit from ArbitrageExecuted event in receipt logs.
        
        Args:
            receipt: Transaction receipt
        
        Returns:
            Realized profit in USDC, or None if not found
        """
        
        try:
            logs = receipt.get('logs', [])
            if not logs:
                return None

            contract = self.arbitrage_executor_contract
            if contract is None:
                return None

            events = contract.events.ArbitrageExecuted().process_receipt(receipt)
            if not events:
                return None

            profit_raw = events[0]['args'].get('profit') or events[0]['args'].get('profitRealized')
            if profit_raw is None:
                return None

            profit_usdc = Decimal(int(profit_raw)) / Decimal(10 ** USDC_DECIMALS)
            _logger.debug(f"PROFIT_EXTRACTED_FROM_LOGS: profit_usdc={profit_usdc}")
            return profit_usdc
        except Exception as e:
            _logger.warning(f"Failed to extract profit from logs: {e}")
        
        return None
    
    def _extract_revert_reason(self, tx: Dict[str, Any], receipt: Dict[str, Any]) -> str:
        """
        Extract revert reason by replaying eth_call at the failed block.
        
        Args:
            tx: Original transaction dict
            receipt: Failed transaction receipt
        
        Returns:
            Revert reason string
        """
        
        try:
            block_number = receipt.get('blockNumber')
            if block_number is None:
                return "Transaction reverted on-chain"

            if self.web3 is None:
                return "Transaction reverted on-chain"

            self.web3.eth.call(tx, block_identifier=max(int(block_number) - 1, 0))
            return "Transaction reverted on-chain"
        except ContractLogicError as e:
            return str(e)
        except Exception as e:
            return f"Unknown revert reason: {str(e)[:100]}"

    def _load_executor_contract(self):
        try:
            with open(ARBITRAGE_EXECUTOR_ABI_PATH, 'r') as handle:
                data = json.load(handle)
            address = data.get('address')
            abi = data.get('abi', [])
            if not address:
                return None
            return self.web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
        except Exception:
            return None

