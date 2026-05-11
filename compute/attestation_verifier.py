"""
Attestation Verification Module

Performs off-chain verification of inference responses before the agent
submits them to the smart contract. This adds a defense-in-depth layer
on top of the on-chain verification in SignalValidator.sol.

Verifies three sequential checks:
1. Signature Recovery Check — recover signer from signature and match to registered TEE
2. Expiry Check — ensure signal hasn't expired
3. Output Hash Integrity Check — verify output hash matches reconstructed value
"""

import os
import json
import time
import hashlib
from typing import Optional, Any
from dataclasses import dataclass
from decimal import Decimal
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode as eth_abi_encode
from eth_utils import keccak


@dataclass
class VerificationResult:
    """Result of inference response verification."""
    passed: bool  # Whether verification succeeded
    failed_check: Optional[str]  # Which check failed (if any)
    recovered_address: Optional[str]  # Recovered signer address
    time_to_expiry_seconds: int  # Seconds until signal expires
    verified_at: int  # Unix timestamp of verification


class VerificationError(Exception):
    """Base exception for verification failures."""
    pass


class AttestationVerifier:
    """
    Off-chain verification of inference responses before on-chain submission.
    
    Independently verifies every signal the agent receives from the TEE
    before submitting it to the smart contract.
    """

    def __init__(self):
        """Initialize the verifier with expected TEE address from environment."""
        self.tee_eth_address = os.getenv("TEE_ETH_ADDRESS")
        if not self.tee_eth_address:
            raise VerificationError(
                "TEE_ETH_ADDRESS environment variable not set"
            )

    def verify_inference_response(self, response: Any) -> VerificationResult:
        """
        Verify an inference response in three sequential checks.

        Args:
            response: InferenceOutput or dict with signal fields and signature

        Returns:
            VerificationResult with detailed diagnostics

        The three checks are:
        1. Signature Recovery — reconstruct message hash, recover signer, check address
        2. Expiry Check — ensure signal hasn't expired (plus 5 second grace period)
        3. Output Hash Integrity — verify output_hash matches reconstructed value
        """
        verified_at = int(time.time())
        recovered_address = None

        try:
            # Extract fields from response (handle both dict and object)
            if isinstance(response, dict):
                fields = response
            else:
                fields = self._response_to_dict(response)

            # Check 1: Signature Recovery
            recovered_address = self._verify_signature(fields)
            if recovered_address.lower() != self.tee_eth_address.lower():
                return VerificationResult(
                    passed=False,
                    failed_check="SIGNATURE_RECOVERY",
                    recovered_address=recovered_address,
                    time_to_expiry_seconds=0,
                    verified_at=verified_at,
                )

            # Check 2: Expiry Check
            time_to_expiry = self._verify_expiry(fields)
            if time_to_expiry < 5:
                return VerificationResult(
                    passed=False,
                    failed_check="EXPIRY_CHECK",
                    recovered_address=recovered_address,
                    time_to_expiry_seconds=time_to_expiry,
                    verified_at=verified_at,
                )

            # Check 3: Output Hash Integrity
            self._verify_output_hash_integrity(fields)

            # All checks passed
            return VerificationResult(
                passed=True,
                failed_check=None,
                recovered_address=recovered_address,
                time_to_expiry_seconds=time_to_expiry,
                verified_at=verified_at,
            )

        except VerificationError as e:
            failure_code = str(e).split(":", 1)[0].strip()
            return VerificationResult(
                passed=False,
                failed_check=failure_code,
                recovered_address=recovered_address,
                time_to_expiry_seconds=0,
                verified_at=verified_at,
            )

    def _response_to_dict(self, response: Any) -> dict:
        """Convert response object to dictionary."""
        return {
            "opportunity_id": getattr(response, "opportunity_id", ""),
            "primary_dex": getattr(response, "primary_dex", ""),
            "counter_dex": getattr(response, "counter_dex", ""),
            "borrow_amount": getattr(response, "borrow_amount", 0),
            "collateral_required": getattr(response, "collateral_required", 0),
            "expected_profit_usdc": getattr(response, "expected_profit_usdc", 0),
            "expiry_timestamp": getattr(response, "expiry_timestamp", 0),
            "chain_id": getattr(response, "chain_id", 0),
            "decision": getattr(response, "decision", ""),
            "risk_score": getattr(response, "risk_score", 0.0),
            "confidence": getattr(response, "confidence", 0.0),
            "reasoning_summary": getattr(response, "reasoning_summary", ""),
            "output_hash": getattr(response, "output_hash", ""),
            "tee_signature": getattr(response, "tee_signature", ""),
        }

    def _verify_signature(self, fields: dict) -> str:
        """
        Verify signature and recover the signer address.

        Args:
            fields: Dictionary with signal fields and tee_signature

        Returns:
            Recovered Ethereum address

        Raises:
            VerificationError: If signature is invalid or recovery fails
        """
        tee_signature = fields.get("tee_signature")
        if not tee_signature:
            raise VerificationError("SIGNATURE_RECOVERY: No signature found")

        # Reconstruct the canonical message hash
        message_hash = self._encode_signal_for_signing(fields)

        try:
            # Recover the signer
            recovered = Account.recover_message(
                encode_defunct(message_hash),
                signature=tee_signature,
            )
            return recovered

        except Exception as e:
            raise VerificationError(
                f"SIGNATURE_RECOVERY: Failed to recover signer: {e}"
            ) from e

    def _verify_expiry(self, fields: dict) -> int:
        """
        Verify signal hasn't expired.

        Args:
            fields: Dictionary with expiry_timestamp

        Returns:
            Seconds until expiry

        Raises:
            VerificationError: If signal has expired
        """
        expiry_timestamp = fields.get("expiry_timestamp", 0)
        now = int(time.time())
        time_to_expiry = expiry_timestamp - now

        if time_to_expiry < 5:
            raise VerificationError(
                f"EXPIRY_CHECK: Signal expired (expires in {time_to_expiry}s)"
            )

        return time_to_expiry

    def _verify_output_hash_integrity(self, fields: dict) -> None:
        """
        Verify the output hash matches the reconstructed value.

        Args:
            fields: Dictionary with output fields and output_hash

        Raises:
            VerificationError: If hashes don't match
        """
        provided_hash = fields.get("output_hash")
        if not provided_hash:
            raise VerificationError(
                "OUTPUT_HASH_INTEGRITY: No output_hash provided"
            )

        # Reconstruct the output hash from fields
        reconstructed_hash = self._compute_output_hash(fields)

        # Normalize to lowercase hex for comparison
        provided_hex = (
            provided_hash.lower()
            if isinstance(provided_hash, str)
            else provided_hash.hex().lower()
        )
        reconstructed_hex = (
            reconstructed_hash.lower()
            if isinstance(reconstructed_hash, str)
            else reconstructed_hash.hex().lower()
        )

        if provided_hex != reconstructed_hex:
            raise VerificationError(
                f"OUTPUT_HASH_INTEGRITY: Hash mismatch\n"
                f"  Provided: {provided_hex}\n"
                f"  Reconstructed: {reconstructed_hex}"
            )

    @staticmethod
    def _encode_signal_for_signing(fields: dict) -> bytes:
        """
        Encode signal fields in canonical order for hashing.

        This must match signal_encoder.py and SignalValidator.sol exactly.

        Type list: ['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256']

        Args:
            fields: Dictionary with signal fields

        Returns:
            Keccak256 hash of ABI-encoded fields
        """
        # Convert USDC amounts to micro-units (multiply by 10^6)
        borrow_amount_int = int(
            (Decimal(str(fields.get("borrow_amount", 0))) * Decimal("1000000"))
            .to_integral_value()
        )
        collateral_int = int(
            (Decimal(str(fields.get("collateral_required", 0))) * Decimal("1000000"))
            .to_integral_value()
        )
        profit_int = int(
            (Decimal(str(fields.get("expected_profit_usdc", 0))) * Decimal("1000000"))
            .to_integral_value()
        )

        # Pad opportunity_id to 32 bytes
        opportunity_id = fields.get("opportunity_id", "")
        if isinstance(opportunity_id, str):
            opportunity_id_bytes = (
                opportunity_id.encode()
                if not opportunity_id.startswith("0x")
                else bytes.fromhex(opportunity_id[2:])
            )
        else:
            opportunity_id_bytes = opportunity_id

        # Ensure it's exactly 32 bytes
        if len(opportunity_id_bytes) < 32:
            opportunity_id_bytes = opportunity_id_bytes.ljust(32, b"\x00")
        else:
            opportunity_id_bytes = opportunity_id_bytes[:32]

        encoded = eth_abi_encode(
            ["bytes32", "address", "address", "uint256", "uint256", "uint256", "uint32", "uint256"],
            [
                opportunity_id_bytes,
                fields.get("primary_dex", "0x0000000000000000000000000000000000000000"),
                fields.get("counter_dex", "0x0000000000000000000000000000000000000000"),
                borrow_amount_int,
                collateral_int,
                profit_int,
                int(fields.get("expiry_timestamp", 0)),
                int(fields.get("chain_id", 0)),
            ],
        )

        return keccak(encoded)

    @staticmethod
    def _compute_output_hash(fields: dict) -> str:
        """
        Compute the output hash from signal fields.

        Args:
            fields: Dictionary with output fields

        Returns:
            Hex-encoded SHA256 hash of canonical output JSON
        """
        # Create canonical output dictionary
        output_dict = {
            "decision": fields.get("decision", ""),
            "expected_profit": str(fields.get("expected_profit_usdc", 0)),
            "risk_score": round(float(fields.get("risk_score", 0.0)), 8),
            "expiry_timestamp": int(fields.get("expiry_timestamp", 0)),
        }

        # Serialize with sorted keys
        canonical_json = json.dumps(output_dict, sort_keys=True, separators=(",", ":"))

        # Hash with SHA256
        hash_obj = hashlib.sha256(canonical_json.encode())
        return "0x" + hash_obj.hexdigest()

    def log_verification_result(
        self, result: VerificationResult, response: Any
    ) -> None:
        """
        Log verification result at appropriate level.

        Args:
            result: The VerificationResult
            response: The original response (for debugging)
        """
        import logging

        logger = logging.getLogger(__name__)

        if result.passed:
            logger.debug(
                f"✓ Signal verified by TEE {result.recovered_address} "
                f"(expires in {result.time_to_expiry_seconds}s)"
            )
        else:
            logger.critical(
                f"✗ Signal verification FAILED: {result.failed_check}\n"
                f"  Recovered: {result.recovered_address}\n"
                f"  Expected TEE: {self.tee_eth_address}\n"
                f"  Time to expiry: {result.time_to_expiry_seconds}s\n"
                f"  Response: {response}"
            )

