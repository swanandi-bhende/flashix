"""
Transaction builder for atomic flashloan execution.
Constructs the exact transaction calldata to submit to LendingPool.flashLoan() on 0G Chain.
"""

import json
import logging
import os
import re
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

from eth_abi import encode
from web3 import Web3
from web3.contract import Contract

from agent.execution_engine import (
    ExecutionRequest,
    TransactionBuildError,
    USDC_ADDRESS,
    USDC_DECIMALS,
    MAX_GAS_UNITS,
)

_logger = logging.getLogger(__name__)

# Path to contract ABIs
LENDING_POOL_ABI_PATH = "contracts/abi/LendingPool.json"
ARBITRAGE_EXECUTOR_ABI_PATH = "contracts/abi/ArbitrageExecutor.json"

# Deployed contract addresses on 0G Chain
LENDING_POOL_ADDRESS = "0x4c580Fb35fBcc2A6D7223984B634ccE7EbE730Ed"


class TransactionBuilder:
    """
    Builds the complete flashloan transaction calldata with ABI-encoded parameters.
    
    Constructs the ArbitrageSignal struct that will be ABI-encoded as the data
    bytes parameter passed through the flashloan callback.
    """
    
    def __init__(self, web3: Optional[Web3] = None):
        """
        Initialize the transaction builder.
        
        Args:
            web3: Web3 instance connected to 0G Chain
        """
        self.web3 = web3
        self.lending_pool_contract: Optional[Contract] = None
        self.arbitrage_executor_contract: Optional[Contract] = None
        
        if self.web3:
            self._load_contracts()
    
    def _load_contracts(self) -> None:
        """Load contract ABIs and initialize contract instances."""
        try:
            # Load LendingPool ABI
            with open(LENDING_POOL_ABI_PATH, "r") as f:
                lending_pool_data = json.load(f)
                abi = lending_pool_data.get("abi", [])
                address = lending_pool_data.get("address", LENDING_POOL_ADDRESS)
            
            self.lending_pool_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=abi
            )
            _logger.debug(f"Loaded LendingPool contract at {address}")
            
            # Load ArbitrageExecutor ABI
            with open(ARBITRAGE_EXECUTOR_ABI_PATH, "r") as f:
                arbitrage_data = json.load(f)
                abi = arbitrage_data.get("abi", [])
                address = arbitrage_data.get("address")

            if address:
                self.arbitrage_executor_contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(address),
                    abi=abi,
                )
                _logger.debug(f"Loaded ArbitrageExecutor contract at {address}")
        
        except (IOError, json.JSONDecodeError, KeyError) as e:
            _logger.warning(f"Failed to load contract ABIs: {e}")
    
    def build_flashloan_tx(
        self, request: ExecutionRequest, wallet_address: str
    ) -> Dict[str, Any]:
        """
        Build the complete flashloan transaction.
        
        Steps:
        1. Load LendingPool ABI and initialize contract instance
        2. Construct ArbitrageSignal struct with signal data
        3. ABI-encode the struct as data bytes
        4. Call lending_pool.functions.flashLoan(...) with encoded data
        5. Build raw transaction dict with gas and fee estimates
        6. Estimate gas and apply 20% buffer
        
        Args:
            request: ExecutionRequest with all parameters
            wallet_address: Address to send transaction from
        
        Returns:
            Dictionary with transaction parameters ready for signing
        
        Raises:
            TransactionBuildError: If any step fails
        """
        
        _logger.debug(
            f"TX_BUILD_START: opportunity_id={request.opportunity_id}, "
            f"wallet_address={wallet_address}"
        )
        
        try:
            # ================================================================
            # STEP 1: Load LendingPool contract
            # ================================================================
            if not self.lending_pool_contract:
                raise TransactionBuildError("LendingPool contract not initialized")
            
            # ================================================================
            # STEP 2: Construct ArbitrageSignal struct
            # ================================================================
            # Convert opportunity_id to bytes32
            opportunity_id_bytes32 = self._string_to_bytes32(request.opportunity_id)
            sig_v, sig_r, sig_s = self._extract_signature_components(request.signal)
            receiver_address = self._executor_receiver_address()
            
            signal_struct = (
                opportunity_id_bytes32,  # bytes32
                Web3.to_checksum_address(request.primary_dex_router),  # address
                Web3.to_checksum_address(request.counter_dex_router),  # address
                int(request.borrow_amount_usdc * (10 ** USDC_DECIMALS)),  # uint256
                int(request.collateral_amount_usdc * (10 ** USDC_DECIMALS)),  # uint256
                int(request.min_profit_usdc * (10 ** USDC_DECIMALS)),  # uint256
                int(request.deadline),  # uint32
                int(sig_v, 16),  # uint8
                bytes.fromhex(sig_r.replace("0x", "")),  # bytes32
                bytes.fromhex(sig_s.replace("0x", "")),  # bytes32
            )
            
            # ================================================================
            # STEP 3: ABI-encode the struct
            # ================================================================
            try:
                encoded_data = encode(
                    ['(bytes32,address,address,uint256,uint256,uint256,uint32,uint8,bytes32,bytes32)'],
                    [signal_struct]
                )
            except Exception as e:
                raise TransactionBuildError(
                    f"Failed to ABI-encode ArbitrageSignal struct: {e}"
                )
            
            _logger.debug(
                f"ARBITRAGE_SIGNAL_ENCODED: opportunity_id={request.opportunity_id}, "
                f"data_length={len(encoded_data)}"
            )
            
            # ================================================================
            # STEP 4: Build flashLoan function call
            # ================================================================
            try:
                flashloan_fn = self.lending_pool_contract.functions.flashLoan(
                    Web3.to_checksum_address(receiver_address),  # receiver
                    Web3.to_checksum_address(request.borrow_token),  # token
                    int(request.borrow_amount_usdc * (10 ** USDC_DECIMALS)),  # amount
                    encoded_data  # data
                )
            except Exception as e:
                raise TransactionBuildError(
                    f"Failed to build flashLoan function call: {e}"
                )
            
            # ================================================================
            # STEP 5: Build raw transaction dict
            # ================================================================
            try:
                # Get current nonce
                nonce = self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(wallet_address),
                    'pending'
                )
                
                # Get current gas prices
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.get('baseFeePerGas', self.web3.to_wei(1, 'gwei'))
                max_fee_per_gas = int(base_fee * 2)
                max_priority_fee_per_gas = self.web3.to_wei(2, 'gwei')
                chain_id = getattr(self.web3.eth, 'chain_id', 16600)
                
                # Build transaction dict
                tx = flashloan_fn.build_transaction({
                    'from': Web3.to_checksum_address(wallet_address),
                    'nonce': nonce,
                    'gas': MAX_GAS_UNITS,  # Will be estimated and replaced
                    'maxFeePerGas': max_fee_per_gas,
                    'maxPriorityFeePerGas': max_priority_fee_per_gas,
                    'chainId': chain_id,
                })
            
            except Exception as e:
                raise TransactionBuildError(
                    f"Failed to build transaction dict: {e}"
                )
            
            _logger.debug(
                f"TX_DICT_BUILT: opportunity_id={request.opportunity_id}, "
                f"nonce={nonce}, max_fee_per_gas={max_fee_per_gas}"
            )
            
            # ================================================================
            # STEP 6: Estimate gas and apply 20% buffer
            # ================================================================
            try:
                gas_estimate = self.web3.eth.estimate_gas(tx)
                tx['gas'] = int(gas_estimate * 1.2)  # 20% buffer
                
                _logger.debug(
                    f"GAS_ESTIMATED: opportunity_id={request.opportunity_id}, "
                    f"estimate={gas_estimate}, with_buffer={tx['gas']}"
                )
            
            except Exception as e:
                _logger.warning(
                    f"Gas estimation failed, using default: {e}. "
                    f"Using MAX_GAS_UNITS={MAX_GAS_UNITS}"
                )
                tx['gas'] = MAX_GAS_UNITS
            
            _logger.debug(
                f"TX_BUILD_SUCCESS: opportunity_id={request.opportunity_id}, "
                f"tx_hash_will_be={tx.get('hash', 'pending')}"
            )
            
            return tx
        
        except TransactionBuildError:
            raise
        except Exception as e:
            _logger.critical(
                f"UNEXPECTED_TX_BUILD_ERROR: opportunity_id={request.opportunity_id}, "
                f"error={str(e)}", exc_info=True
            )
            raise TransactionBuildError(f"Unexpected error building transaction: {e}")
    
    @staticmethod
    def _string_to_bytes32(s: str) -> bytes:
        """
        Convert a string to bytes32 (padded with zeros).
        
        Args:
            s: String to convert
        
        Returns:
            bytes32 value
        """
        s_bytes = s.encode('utf-8')[:32]
        return s_bytes.ljust(32, b'\x00')

    def _executor_receiver_address(self) -> str:
        if not self.arbitrage_executor_contract:
            raise TransactionBuildError("ArbitrageExecutor contract not initialized")
        return self.arbitrage_executor_contract.address

    @staticmethod
    def _extract_signature_components(signal: Any) -> Tuple[str, str, str]:
        v = getattr(signal, "tee_signature_v", None)
        r = getattr(signal, "tee_signature_r", None)
        s = getattr(signal, "tee_signature_s", None)
        if v is not None and r is not None and s is not None:
            return (f"{int(v):02x}", str(r), str(s))

        signature = getattr(signal, "tee_signature", "") or ""
        signature = signature[2:] if signature.startswith("0x") else signature
        if not re.fullmatch(r"[0-9a-fA-F]+", signature):
            raise TransactionBuildError("tee_signature must be hex-encoded")
        if len(signature) == 130:
            r = signature[:64]
            s = signature[64:128]
            v = signature[128:130]
            return (v, f"0x{r}", f"0x{s}")
        if len(signature) == 128:
            r = signature[:64]
            s = signature[64:128]
            return ("1b", f"0x{r}", f"0x{s}")
        raise TransactionBuildError("Unsupported tee_signature format")
