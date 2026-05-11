"""
Contract interaction utilities for the Flashix arbitrage agent.

This module provides a clean, high-level API for interacting with deployed smart contracts
(LendingPool, ArbitrageExecutor, SignalValidator) without requiring direct ABI calls.
"""

import json
import os
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt
import logging

logger = logging.getLogger(__name__)

# Path to contract ABIs
CONTRACTS_DIR = Path(__file__).parent.parent / "contracts" / "abi"
DEPLOYMENTS_FILE = Path(__file__).parent.parent / "contracts" / "deployments" / "testnet.json"


class ContractInteractionError(Exception):
    """Raised when contract interaction fails."""
    pass


class ContractNotDeployedError(ContractInteractionError):
    """Raised when a required contract is not deployed."""
    pass


class ContractManager:
    """Manages interactions with all three smart contracts."""

    def __init__(self, web3: Web3, network: str = "zgTestnet"):
        """
        Initialize contract manager.

        Args:
            web3: Web3 instance for RPC communication
            network: Network name ("zgTestnet" or "zgMainnet")
        """
        self.web3 = web3
        self.network = network
        self._lending_pool: Optional[Contract] = None
        self._arbitrage_executor: Optional[Contract] = None
        self._signal_validator: Optional[Contract] = None
        self._contracts_loaded = False

        # Load contract deployments
        self._load_deployments()

    def _load_deployments(self) -> None:
        """Load contract addresses and ABIs from deployment artifacts."""
        # Try to load from deployments file first
        if DEPLOYMENTS_FILE.exists():
            with open(DEPLOYMENTS_FILE) as f:
                deployments = json.load(f)
                contracts = deployments.get("contracts", {})
                self.lending_pool_address = contracts.get("LendingPool", {}).get("address")
                self.arbitrage_executor_address = contracts.get("ArbitrageExecutor", {}).get("address")
                self.signal_validator_address = contracts.get("SignalValidator", {}).get("address")
        else:
            # Try to load from environment variables
            self.lending_pool_address = os.getenv("LENDING_POOL_ADDRESS")
            self.arbitrage_executor_address = os.getenv("ARBITRAGE_EXECUTOR_ADDRESS")
            self.signal_validator_address = os.getenv("SIGNAL_VALIDATOR_ADDRESS")

        # Log loaded addresses
        logger.info(f"Loaded contract addresses from {self.network}:")
        logger.info(f"  LendingPool: {self.lending_pool_address}")
        logger.info(f"  ArbitrageExecutor: {self.arbitrage_executor_address}")
        logger.info(f"  SignalValidator: {self.signal_validator_address}")

    def _load_abi(self, contract_name: str) -> Dict[str, Any]:
        """Load ABI from JSON file."""
        abi_path = CONTRACTS_DIR / f"{contract_name}.json"
        if not abi_path.exists():
            raise ContractNotDeployedError(f"ABI not found for {contract_name} at {abi_path}")

        with open(abi_path) as f:
            data = json.load(f)
            return data.get("abi", [])

    def get_lending_pool(self) -> Contract:
        """
        Get initialized LendingPool contract instance.

        Returns:
            Web3 Contract instance for LendingPool

        Raises:
            ContractNotDeployedError: If LendingPool not deployed
        """
        if not self._lending_pool:
            if not self.lending_pool_address:
                raise ContractNotDeployedError("LENDING_POOL_ADDRESS not configured")

            abi = self._load_abi("LendingPool")
            self._lending_pool = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.lending_pool_address),
                abi=abi
            )

        return self._lending_pool

    def get_arbitrage_executor(self) -> Contract:
        """
        Get initialized ArbitrageExecutor contract instance.

        Returns:
            Web3 Contract instance for ArbitrageExecutor

        Raises:
            ContractNotDeployedError: If ArbitrageExecutor not deployed
        """
        if not self._arbitrage_executor:
            if not self.arbitrage_executor_address:
                raise ContractNotDeployedError("ARBITRAGE_EXECUTOR_ADDRESS not configured")

            abi = self._load_abi("ArbitrageExecutor")
            self._arbitrage_executor = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.arbitrage_executor_address),
                abi=abi
            )

        return self._arbitrage_executor

    def get_signal_validator(self) -> Contract:
        """
        Get initialized SignalValidator contract instance.

        Returns:
            Web3 Contract instance for SignalValidator

        Raises:
            ContractNotDeployedError: If SignalValidator not deployed
        """
        if not self._signal_validator:
            if not self.signal_validator_address:
                raise ContractNotDeployedError("SIGNAL_VALIDATOR_ADDRESS not configured")

            abi = self._load_abi("SignalValidator")
            self._signal_validator = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.signal_validator_address),
                abi=abi
            )

        return self._signal_validator

    def get_max_flashloan(self, token_address: str) -> int:
        """
        Get maximum flashloan available for a token.

        Args:
            token_address: ERC-20 token address

        Returns:
            Maximum flashloan amount in token units

        Raises:
            ContractInteractionError: If call fails
        """
        try:
            lending_pool = self.get_lending_pool()
            token_addr = Web3.to_checksum_address(token_address)
            max_loan = lending_pool.functions.maxFlashLoan(token_addr).call()
            return max_loan
        except Exception as e:
            raise ContractInteractionError(f"Failed to get max flashloan: {str(e)}")

    def get_current_fee(self, token_address: str, amount: int) -> int:
        """
        Get flashloan fee for a given amount.

        Args:
            token_address: ERC-20 token address
            amount: Loan amount in token units

        Returns:
            Fee amount in token units

        Raises:
            ContractInteractionError: If call fails
        """
        try:
            lending_pool = self.get_lending_pool()
            token_addr = Web3.to_checksum_address(token_address)
            fee = lending_pool.functions.flashFee(token_addr, amount).call()
            return fee
        except Exception as e:
            raise ContractInteractionError(f"Failed to get flashloan fee: {str(e)}")

    def execute_flashloan(
        self,
        token_address: str,
        amount: int,
        signal_data: bytes,
        signer: Any,
        trace_id: Optional[str] = None,
        gas_limit: Optional[int] = None
    ) -> str:
        """
        Execute a flashloan transaction.

        Args:
            token_address: ERC-20 token to borrow
            amount: Amount to borrow in token units
            signal_data: Encoded arbitrage signal
            signer: Web3 account that will sign the transaction
            trace_id: Optional reasoning trace identifier for audit correlation
            gas_limit: Optional gas limit (auto-estimated if not provided)

        Returns:
            Transaction hash

        Raises:
            ContractInteractionError: If transaction fails
        """
        try:
            lending_pool = self.get_lending_pool()
            arbitrage_executor = self.get_arbitrage_executor()

            if trace_id:
                trace_tag = Web3.keccak(text=trace_id)
                signal_data = signal_data + trace_tag

            token_addr = Web3.to_checksum_address(token_address)
            executor_addr = arbitrage_executor.address

            # Build transaction
            tx = lending_pool.functions.flashLoan(
                executor_addr,
                token_addr,
                amount,
                signal_data
            ).build_transaction({
                'from': signer.address,
                'nonce': self.web3.eth.get_transaction_count(signer.address),
                'gas': gas_limit or self.web3.eth.estimate_gas(
                    lending_pool.functions.flashLoan(
                        executor_addr,
                        token_addr,
                        amount,
                        signal_data
                    ).build_transaction({'from': signer.address})
                ),
                'gasPrice': self.web3.eth.gas_price,
            })

            # Sign and send transaction
            signed_tx = signer.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            logger.info(
                "Flashloan transaction submitted: %s trace_id=%s",
                tx_hash.hex(),
                trace_id,
            )
            return tx_hash.hex()

        except Exception as e:
            raise ContractInteractionError(f"Failed to execute flashloan: {str(e)}")

    def wait_for_confirmation(
        self,
        tx_hash: str,
        confirmations: int = 2,
        timeout: int = 300
    ) -> TxReceipt:
        """
        Wait for transaction confirmation.

        Args:
            tx_hash: Transaction hash to wait for
            confirmations: Number of confirmations to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Transaction receipt

        Raises:
            ContractInteractionError: If transaction fails or times out
        """
        try:
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

            if receipt['status'] == 1:
                logger.info(f"Transaction confirmed: {tx_hash}")
                return receipt
            else:
                raise ContractInteractionError(f"Transaction failed: {tx_hash}")

        except Exception as e:
            raise ContractInteractionError(f"Failed to wait for confirmation: {str(e)}")

    def get_accumulated_fees(self, token_address: str) -> int:
        """
        Get accumulated fees for a token in the lending pool.

        Args:
            token_address: ERC-20 token address

        Returns:
            Accumulated fees in token units

        Raises:
            ContractInteractionError: If call fails
        """
        try:
            lending_pool = self.get_lending_pool()
            token_addr = Web3.to_checksum_address(token_address)
            fees = lending_pool.functions.getAccumulatedFees(token_addr).call()
            return fees
        except Exception as e:
            raise ContractInteractionError(f"Failed to get accumulated fees: {str(e)}")

    def get_execution_count(self) -> int:
        """
        Get total number of arbitrage executions.

        Returns:
            Number of successful executions

        Raises:
            ContractInteractionError: If call fails
        """
        try:
            executor = self.get_arbitrage_executor()
            count = executor.functions.getExecutionCount().call()
            return count
        except Exception as e:
            raise ContractInteractionError(f"Failed to get execution count: {str(e)}")

    def verify_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Verify a signal through SignalValidator.

        Args:
            signal: Arbitrage signal dictionary

        Returns:
            True if signal is valid

        Raises:
            ContractInteractionError: If verification fails
        """
        try:
            validator = self.get_signal_validator()
            result = validator.functions.verify(signal).call()
            return result
        except Exception as e:
            raise ContractInteractionError(f"Signal verification failed: {str(e)}")

    def test_contract_connectivity(self) -> Dict[str, bool]:
        """
        Test connectivity to all contracts.

        Returns:
            Dictionary with contract names as keys and connectivity status as values
        """
        results = {}

        for contract_name, getter in [
            ("LendingPool", self.get_lending_pool),
            ("ArbitrageExecutor", self.get_arbitrage_executor),
            ("SignalValidator", self.get_signal_validator),
        ]:
            try:
                contract = getter()
                # Try a simple read call
                if contract_name == "LendingPool":
                    contract.functions.FEE_BPS().call()
                elif contract_name == "SignalValidator":
                    contract.functions.getTrustedSigner().call()
                elif contract_name == "ArbitrageExecutor":
                    contract.functions.getExecutionCount().call()

                results[contract_name] = True
                logger.info(f"✓ {contract_name} responsive")
            except Exception as e:
                results[contract_name] = False
                logger.error(f"✗ {contract_name} not responsive: {str(e)}")

        return results


def initialize_contracts(rpc_url: str, network: str = "zgTestnet") -> ContractManager:
    """
    Initialize contract manager with Web3 connection.

    Args:
        rpc_url: 0G Chain RPC endpoint URL
        network: Network name

    Returns:
        Initialized ContractManager instance

    Raises:
        ContractInteractionError: If Web3 connection fails
    """
    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not web3.is_connected():
            raise ContractInteractionError(f"Failed to connect to {rpc_url}")

        logger.info(f"Connected to {network} at {rpc_url}")
        return ContractManager(web3, network)

    except Exception as e:
        raise ContractInteractionError(f"Failed to initialize contracts: {str(e)}")
