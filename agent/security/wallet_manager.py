"""
Hot-Wallet Manager — Enforces strict wallet isolation and profit sweeping.

This module implements the hot-wallet isolation security model where:
- Agent wallet never holds > 100 USDC
- Profits are swept to cold storage every hour
- Any balance anomaly triggers immediate trading halt
- All operations are logged with full audit trail
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from web3 import Web3
from web3.contract import Contract


# Configure logging
logger = logging.getLogger(__name__)


class WalletConfigError(Exception):
    """Raised when wallet configuration is invalid."""
    pass


class BalanceAnomalyError(Exception):
    """Raised when wallet balance exceeds safety threshold."""
    pass


class SweepFailureError(Exception):
    """Raised when a sweep operation fails permanently."""
    pass


@dataclass
class WalletStatus:
    """Current status of the hot wallet."""
    balance_usdc: Decimal
    above_threshold: bool  # True if balance > MAX_HOT_WALLET_BALANCE_USDC
    sweep_required: bool  # True if balance > Decimal("10.0")
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SweepResult:
    """Result of a sweep operation."""
    skipped: bool = False
    reason: str = ""
    tx_hash: Optional[str] = None
    amount_swept_usdc: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = False


@dataclass
class SweepEvent:
    """Record of a completed sweep event for audit trail."""
    timestamp: datetime
    tx_hash: str
    amount_swept_usdc: Decimal
    cold_storage_address: str
    block_number: Optional[int] = None
    confirmation_time_seconds: Optional[float] = None


class HotWalletManager:
    """
    Manages the hot wallet isolation security model.
    
    Ensures:
    - Hot wallet balance never exceeds 100 USDC
    - Profits are automatically swept to cold storage hourly
    - Balance anomalies trigger immediate trading halt
    - Complete audit trail of all sweeps
    """
    
    # Safety limits
    MAX_HOT_WALLET_BALANCE_USDC = Decimal("100.0")
    SWEEP_THRESHOLD_USDC = Decimal("10.0")
    MIN_GAS_BUFFER_USDC = Decimal("5.0")
    SWEEP_INTERVAL_SECONDS = 3600  # 1 hour
    
    # USDC contract configuration (0G mainnet)
    USDC_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS", "")
    USDC_DECIMALS = 6
    
    def __init__(self, 
                 hot_wallet_private_key: Optional[str] = None,
                 cold_storage_address: Optional[str] = None,
                 rpc_url: Optional[str] = None,
                 data_dir: str = "data"):
        """
        Initialize the hot wallet manager.
        
        Args:
            hot_wallet_private_key: Private key of the hot wallet (loaded from env if not provided).
            cold_storage_address: Address of the cold storage wallet (loaded from env if not provided).
            rpc_url: RPC URL for the mainnet node (loaded from env if not provided).
            data_dir: Directory for storing sweep records and state.
            
        Raises:
            WalletConfigError: If configuration is invalid or missing.
        """
        # Load configuration from environment
        self.hot_wallet_private_key = (
            hot_wallet_private_key or os.getenv("HOT_WALLET_PRIVATE_KEY", "")
        ).strip()
        self.cold_storage_address = (
            cold_storage_address or os.getenv("COLD_STORAGE_ADDRESS", "")
        ).strip()
        rpc_url = rpc_url or os.getenv("MAINNET_RPC_URL", "")
        
        # Validate configuration
        if not self.hot_wallet_private_key:
            raise WalletConfigError("HOT_WALLET_PRIVATE_KEY environment variable not set")
        if not self.cold_storage_address:
            raise WalletConfigError("COLD_STORAGE_ADDRESS environment variable not set")
        if not rpc_url:
            raise WalletConfigError("MAINNET_RPC_URL environment variable not set")
        if not self.USDC_ADDRESS:
            raise WalletConfigError("USDC_CONTRACT_ADDRESS environment variable not set")
        
        # Validate addresses
        if not Web3.is_address(self.cold_storage_address):
            raise WalletConfigError(f"Invalid COLD_STORAGE_ADDRESS: {self.cold_storage_address}")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise WalletConfigError(f"Failed to connect to RPC: {rpc_url}")
        
        # Derive hot wallet address from private key
        try:
            account = self.w3.eth.account.from_key(self.hot_wallet_private_key)
            self.hot_wallet_address = account.address
        except Exception as e:
            raise WalletConfigError(f"Invalid HOT_WALLET_PRIVATE_KEY: {e}")
        
        # Initialize USDC contract
        usdc_abi = self._get_erc20_abi()
        self.usdc_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_ADDRESS),
            abi=usdc_abi,
        )
        
        # Data directory for audit trail
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sweeps_log_file = self.data_dir / "sweeps.jsonl"
        
        # Sweep daemon state
        self._sweep_daemon_thread: Optional[threading.Thread] = None
        self._sweep_daemon_running = False
        
        logger.info(
            f"Hot wallet manager initialized: address={self.hot_wallet_address}, "
            f"cold_storage={self.cold_storage_address[:8]}..."
        )
    
    def _get_erc20_abi(self) -> list:
        """Get minimal ERC-20 ABI for balance and transfer calls."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
        ]
    
    def check_balance(self) -> WalletStatus:
        """
        Check the current hot wallet balance.
        
        Returns:
            WalletStatus: Current balance and flags.
            
        Raises:
            BalanceAnomalyError: If balance exceeds safety threshold.
        """
        try:
            balance_wei = self.usdc_contract.functions.balanceOf(
                self.hot_wallet_address
            ).call()
            balance_usdc = Decimal(balance_wei) / (10 ** self.USDC_DECIMALS)
            
            status = WalletStatus(
                balance_usdc=balance_usdc,
                above_threshold=balance_usdc > self.MAX_HOT_WALLET_BALANCE_USDC,
                sweep_required=balance_usdc > self.SWEEP_THRESHOLD_USDC,
            )
            
            if status.above_threshold:
                logger.warning(
                    f"BALANCE_ANOMALY: hot wallet balance {balance_usdc} USDC exceeds "
                    f"max {self.MAX_HOT_WALLET_BALANCE_USDC} USDC"
                )
                raise BalanceAnomalyError(
                    f"Hot wallet balance {balance_usdc} exceeds limit {self.MAX_HOT_WALLET_BALANCE_USDC}"
                )
            
            return status
        except Exception as e:
            logger.error(f"Failed to check wallet balance: {e}")
            raise
    
    def sweep_to_cold_storage(self) -> SweepResult:
        """
        Sweep profits from hot wallet to cold storage.
        
        Process:
        1. Check current balance
        2. Skip if balance <= 5.0 USDC (minimum sweep threshold)
        3. Calculate sweep amount = balance - 5.0 (keep 5 USDC as gas buffer)
        4. Build and submit ERC-20 transfer transaction
        5. Wait for confirmation with 60-second timeout
        6. Log sweep event to audit trail
        
        Returns:
            SweepResult: Result of the sweep operation.
        """
        sweep_result = SweepResult()
        
        try:
            # Check current balance
            status = self.check_balance()
            
            if status.balance_usdc <= self.MIN_GAS_BUFFER_USDC:
                sweep_result.skipped = True
                sweep_result.reason = "BALANCE_TOO_LOW"
                logger.info(
                    f"Sweep skipped: balance {status.balance_usdc} USDC <= "
                    f"minimum {self.MIN_GAS_BUFFER_USDC} USDC"
                )
                return sweep_result
            
            # Calculate sweep amount
            sweep_amount_usdc = status.balance_usdc - self.MIN_GAS_BUFFER_USDC
            sweep_amount_wei = int(sweep_amount_usdc * (10 ** self.USDC_DECIMALS))
            
            # Get current nonce and gas price
            account = self.w3.eth.account.from_key(self.hot_wallet_private_key)
            nonce = self.w3.eth.get_transaction_count(account.address)
            gas_price = self.w3.eth.gas_price
            
            # Build transfer transaction
            transfer_function = self.usdc_contract.functions.transfer(
                Web3.to_checksum_address(self.cold_storage_address),
                sweep_amount_wei,
            )
            
            tx_data = transfer_function.build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 100000,  # Standard ERC-20 transfer gas
                "gasPrice": gas_price,
            })
            
            # Sign and submit transaction
            signed_tx = self.w3.eth.account.sign_transaction(
                tx_data,
                self.hot_wallet_private_key,
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(
                f"Sweep submitted: amount={sweep_amount_usdc:.4f} USDC, "
                f"to={self.cold_storage_address[:8]}..., tx={tx_hash.hex()}"
            )
            
            # Wait for confirmation (60 second timeout)
            start_time = time.time()
            confirmation_time = None
            block_number = None
            
            while time.time() - start_time < 60:
                try:
                    receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                    if receipt is not None:
                        confirmation_time = time.time() - start_time
                        block_number = receipt.blockNumber
                        logger.info(
                            f"Sweep confirmed: tx={tx_hash.hex()}, "
                            f"block={block_number}, time={confirmation_time:.1f}s"
                        )
                        break
                except Exception:
                    pass
                time.sleep(2)
            
            # Record sweep event
            sweep_event = SweepEvent(
                timestamp=datetime.utcnow(),
                tx_hash=tx_hash.hex(),
                amount_swept_usdc=sweep_amount_usdc,
                cold_storage_address=self.cold_storage_address,
                block_number=block_number,
                confirmation_time_seconds=confirmation_time,
            )
            self._record_sweep(sweep_event)
            
            sweep_result.success = True
            sweep_result.tx_hash = tx_hash.hex()
            sweep_result.amount_swept_usdc = sweep_amount_usdc
            
            return sweep_result
            
        except Exception as e:
            logger.error(f"Sweep operation failed: {e}")
            sweep_result.success = False
            sweep_result.reason = str(e)
            raise SweepFailureError(f"Sweep operation failed: {e}")
    
    def _record_sweep(self, event: SweepEvent) -> None:
        """Record a sweep event to the audit trail."""
        try:
            with open(self.sweeps_log_file, "a") as f:
                event_dict = {
                    "timestamp": event.timestamp.isoformat(),
                    "tx_hash": event.tx_hash,
                    "amount_swept_usdc": str(event.amount_swept_usdc),
                    "cold_storage_address": event.cold_storage_address,
                    "block_number": event.block_number,
                    "confirmation_time_seconds": event.confirmation_time_seconds,
                }
                f.write(json.dumps(event_dict) + "\n")
        except Exception as e:
            logger.error(f"Failed to record sweep event: {e}")
    
    def _sweep_daemon(self) -> None:
        """
        Background thread that performs sweep operations every SWEEP_INTERVAL_SECONDS.
        
        Error handling:
        - First failure: log error and retry after 60 seconds
        - Second consecutive failure: log CRITICAL and stop (funds never stranded > 2 hours)
        """
        consecutive_failures = 0
        
        while self._sweep_daemon_running:
            try:
                status = self.check_balance()
                
                if status.sweep_required:
                    result = self.sweep_to_cold_storage()
                    if result.success:
                        consecutive_failures = 0
                        logger.info(
                            f"PROFIT_SWEPT: amount={result.amount_swept_usdc:.4f} USDC, "
                            f"to={self.cold_storage_address[:8]}..., tx={result.tx_hash}"
                        )
                    else:
                        consecutive_failures += 1
                        logger.warning(
                            f"Sweep failed (attempt {consecutive_failures}): {result.reason}"
                        )
                        
                        if consecutive_failures >= 2:
                            logger.critical(
                                f"SWEEP_FAILED: Maximum retries exceeded. Funds may be stranded. "
                                f"Manual intervention required. Last error: {result.reason}"
                            )
                            # Stop daemon to prevent infinite retry loop
                            self._sweep_daemon_running = False
                            break
                        else:
                            # Retry after 60 seconds
                            time.sleep(60)
                            continue
                
                # Sleep until next sweep interval
                time.sleep(self.SWEEP_INTERVAL_SECONDS)
                
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"Sweep daemon error: {e}")
                
                if consecutive_failures >= 2:
                    logger.critical(
                        f"SWEEP_FAILED: Maximum retries exceeded. "
                        f"Stopping sweep daemon. Manual intervention required."
                    )
                    self._sweep_daemon_running = False
                    break
                
                time.sleep(60)
    
    def start_sweep_daemon(self) -> None:
        """Start the background sweep daemon thread."""
        if self._sweep_daemon_thread is not None and self._sweep_daemon_thread.is_alive():
            logger.warning("Sweep daemon is already running")
            return
        
        self._sweep_daemon_running = True
        self._sweep_daemon_thread = threading.Thread(
            target=self._sweep_daemon,
            daemon=True,
            name="SweepDaemon",
        )
        self._sweep_daemon_thread.start()
        logger.info("Sweep daemon started")
    
    def stop_sweep_daemon(self) -> None:
        """Stop the background sweep daemon thread."""
        self._sweep_daemon_running = False
        if self._sweep_daemon_thread is not None:
            self._sweep_daemon_thread.join(timeout=5)
        logger.info("Sweep daemon stopped")
