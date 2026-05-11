"""
TEE Attestation Quote Generation and Formatting

Handles the generation, formatting, and export of TEE attestation artifacts
needed to establish hardware-level trust with the on-chain verifier.

In hardware SGX mode: calls sgx_create_report() with the enclave's public key
embedded in the report_data field, allowing the attestation quote to
cryptographically bind the hardware measurement to the specific public key.

In simulation mode: generates a mock attestation report with the same structure
but clearly flagged as SIMULATION, suitable for development and testing.
"""

import os
import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Literal, Optional


@dataclass
class AttestationReport:
    """
    Complete TEE attestation report data.
    
    This structure matches the output of Intel SGX attestation and includes
    all fields needed for on-chain registration and verification.
    """
    mrenclave: str  # 32-byte hex hash of enclave binary
    mrsigner: str  # 32-byte hex hash of enclave signing key
    public_key: str  # hex-encoded secp256k1 public key (uncompressed, 0x04...)
    eth_address: str  # Ethereum address
    isvsvn: int  # Enclave security version number
    quote_body: str  # hex-encoded raw SGX quote (or mock quote in simulation)
    ias_signature: str  # Intel Attestation Service signature over the quote (or mock in simulation)
    attestation_type: Literal["SGX_HARDWARE", "TDX_HARDWARE", "SIMULATION"]  # Type of attestation
    generated_at: int  # Unix timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OnChainRegistrationData:
    """
    Minimal data needed for on-chain TEE registration.
    
    This is the subset of AttestationReport that SignalValidator.sol requires
    for the registerTEE() call. Other fields are stripped for efficiency.
    """
    eth_address: str
    mrenclave: str
    attestation_type: str
    generated_at: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class AttestationError(Exception):
    """Base exception for attestation operations."""
    pass


class AttestationGenerator:
    """
    Generate and format TEE attestation quotes and reports.
    
    Supports both hardware SGX attestation and simulation mode for development.
    """

    def __init__(self, mode: str = "simulation"):
        """
        Initialize the attestation generator.

        Args:
            mode: "simulation" (for development) or "sgx_hardware" (for Intel SGX)
        """
        self.mode = mode
        if mode not in ["simulation", "sgx_hardware", "tdx_hardware"]:
            raise AttestationError(f"Invalid attestation mode: {mode}")

    def generate_quote(self, public_key: str) -> AttestationReport:
        """
        Generate an attestation quote for the given public key.

        In hardware mode: Calls sgx_create_report() with the public key in
        report_data, producing a quote signed by Intel IAS.

        In simulation mode: Generates a mock quote with the same structure.

        Args:
            public_key: hex-encoded secp256k1 public key (0x04...)

        Returns:
            AttestationReport with all fields populated

        Raises:
            AttestationError: If quote generation fails
        """
        try:
            if self.mode == "sgx_hardware":
                return self._generate_sgx_quote(public_key)
            elif self.mode == "tdx_hardware":
                return self._generate_tdx_quote(public_key)
            else:
                return self._generate_simulation_quote(public_key)

        except Exception as e:
            raise AttestationError(f"Failed to generate attestation quote: {e}") from e

    def _generate_sgx_quote(self, public_key: str) -> AttestationReport:
        """
        Generate a real SGX hardware attestation quote.

        In production, this would call sgx_create_report() via the enclave host.
        For now, we provide a placeholder that would be implemented when
        running on actual SGX hardware.

        Args:
            public_key: hex-encoded secp256k1 public key

        Returns:
            AttestationReport

        Raises:
            AttestationError: If SGX operations fail
        """
        # In real hardware:
        # 1. Call sgx_create_report() with public_key in report_data (zero-padded to 64 bytes)
        # 2. Get the report from the enclave
        # 3. Send to Intel Attestation Service (IAS) for signing
        # 4. Retrieve the signed quote
        # 5. Extract MRENCLAVE, MRSIGNER, etc. from the quote

        # For now, raise an error indicating hardware mode is not yet supported
        raise AttestationError(
            "SGX hardware attestation not yet implemented. "
            "Use simulation mode for development."
        )

    def _generate_tdx_quote(self, public_key: str) -> AttestationReport:
        """
        Generate a TDX hardware attestation quote.

        Similar to SGX, but for Intel TDX (Trusted Domain Extensions).

        Args:
            public_key: hex-encoded secp256k1 public key

        Returns:
            AttestationReport

        Raises:
            AttestationError: If TDX operations fail
        """
        raise AttestationError(
            "TDX hardware attestation not yet implemented. "
            "Use simulation mode for development."
        )

    def _generate_simulation_quote(self, public_key: str) -> AttestationReport:
        """
        Generate a mock attestation quote for development and testing.

        This quote is clearly flagged as SIMULATION and should never be
        used on mainnet. It demonstrates the structure and allows testing
        the full cryptographic pipeline without hardware.

        Args:
            public_key: hex-encoded secp256k1 public key

        Returns:
            AttestationReport with attestation_type="SIMULATION"
        """
        # Get or create MRENCLAVE
        mrenclave = os.getenv("TEE_MRENCLAVE", "0x" + "0" * 64)

        # Derive MRSIGNER from the public key (mock - in real SGX, this comes from hardware)
        mrsigner_bytes = hashlib.sha256(public_key.encode()).digest()
        mrsigner = "0x" + mrsigner_bytes.hex()

        # Get ISV SVN (Security Version Number) - mock value
        isvsvn = int(os.getenv("TEE_ISV_SVN", "1"))

        # Create mock quote body (in real SGX, this is the raw quote bytes)
        # Structure: version (1 byte) + mrenclave (32) + mrsigner (32) + reserved (64) + public_key (65)
        mock_quote_data = {
            "version": "0x03",  # SGX quote version 3
            "mrenclave": mrenclave,
            "mrsigner": mrsigner,
            "isvsvn": isvsvn,
            "public_key": public_key,
            "generated_at": int(datetime.utcnow().timestamp()),
        }
        quote_body = "0x" + json.dumps(mock_quote_data).encode().hex()

        # Create mock IAS signature (in real SGX, this is signed by Intel)
        ias_signature = "0x" + hashlib.sha256(quote_body.encode()).digest().hex()

        return AttestationReport(
            mrenclave=mrenclave,
            mrsigner=mrsigner,
            public_key=public_key,
            eth_address=self._derive_eth_address(public_key),
            isvsvn=isvsvn,
            quote_body=quote_body,
            ias_signature=ias_signature,
            attestation_type="SIMULATION",
            generated_at=int(datetime.utcnow().timestamp()),
        )

    @staticmethod
    def _derive_eth_address(public_key: str) -> str:
        """
        Derive the Ethereum address from a secp256k1 public key.

        Args:
            public_key: hex-encoded uncompressed secp256k1 public key (0x04...)

        Returns:
            Ethereum address (0x... format)
        """
        from eth_keys import keys

        try:
            # Remove 0x04 prefix (uncompressed point marker)
            pub_key_bytes = bytes.fromhex(public_key[2:] if public_key.startswith("0x") else public_key)

            # eth_keys expects the uncompressed key without the 0x04 prefix
            if pub_key_bytes[0] == 0x04:
                pub_key_bytes = pub_key_bytes[1:]

            pk = keys.PublicKey(pub_key_bytes)
            address = pk.to_checksum_address()
            return address

        except Exception:
            # Fallback: Use Keccak-256 hash
            from eth_utils import keccak

            pub_key_bytes = bytes.fromhex(public_key[2:] if public_key.startswith("0x") else public_key)
            if pub_key_bytes[0] == 0x04:
                pub_key_bytes = pub_key_bytes[1:]

            address_bytes = keccak(pub_key_bytes)[-20:]
            return "0x" + address_bytes.hex()

    def export_for_onchain(self, report: AttestationReport) -> OnChainRegistrationData:
        """
        Export the attestation report in a format suitable for on-chain registration.

        Strips away the raw quote bytes and other fields not needed by the smart contract,
        returning only the minimal set required for SignalValidator.registerTEE().

        Args:
            report: AttestationReport from generate_quote()

        Returns:
            OnChainRegistrationData with only eth_address, mrenclave, attestation_type, generated_at
        """
        return OnChainRegistrationData(
            eth_address=report.eth_address,
            mrenclave=report.mrenclave,
            attestation_type=report.attestation_type,
            generated_at=report.generated_at,
        )

    def export_full_report(self, report: AttestationReport) -> dict:
        """
        Export the full attestation report for audit and verification purposes.

        This includes all fields and is suitable for storing in audit logs,
        sending to off-chain auditors, or for completeness checking.

        Args:
            report: AttestationReport from generate_quote()

        Returns:
            Dictionary with all report fields
        """
        return report.to_dict()

    @staticmethod
    def parse_onchain_data(data: dict) -> OnChainRegistrationData:
        """
        Parse on-chain registration data back into a structured format.

        This is useful for auditing and verification.

        Args:
            data: Dictionary returned by export_for_onchain()

        Returns:
            OnChainRegistrationData
        """
        return OnChainRegistrationData(**data)
