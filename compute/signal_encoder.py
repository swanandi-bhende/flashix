"""
Signal Encoder Module

Canonical encoding of InferenceOutput fields into the byte sequence that both
the TEE signer (Python) and the smart contract verifier (Solidity) operate on.

This is the single source of truth for how signals are encoded. Any discrepancy
between Python and Solidity encoding causes every signature verification to fail,
making this the most critical precision engineering task in the cryptographic pipeline.

The canonical encoding uses Solidity's abi.encode() format, which must be
replicated exactly in Python using eth_abi.encode().
"""

from decimal import Decimal
from typing import Any, Dict, Tuple
from eth_abi import encode as eth_abi_encode
from eth_utils import keccak


class EncodingError(Exception):
    """Raised when signal encoding fails."""
    pass


class SignalEncoder:
    """
    Encodes and decodes arbitrage signals in canonical ABI-encoded format.
    
    The canonical format is:
      abi.encode(
        ['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256'],
        [opportunityId, primaryDex, counterDex, borrowAmount, collateralRequired, expectedProfit, expiryTimestamp, chainId]
      )
    
    Note the critical detail: USDC-denominated amounts are multiplied by 10^6
    before encoding (6 decimal places for USDC).
    """

    # Canonical ABI type list (must match Solidity exactly)
    CANONICAL_TYPES = [
        "bytes32",   # opportunity_id (padded to 32 bytes)
        "address",   # primary_dex
        "address",   # counter_dex
        "uint256",   # borrow_amount (in micro-units, i.e., * 10^6)
        "uint256",   # collateral_required (in micro-units)
        "uint256",   # expected_profit (in micro-units)
        "uint32",    # expiry_timestamp (Unix timestamp)
        "uint256",   # chain_id (network identifier)
    ]

    @staticmethod
    def encode_for_signing(signal_dict: Dict[str, Any]) -> bytes:
        """
        Encode a signal dictionary into canonical ABI-encoded bytes for signing.

        Args:
            signal_dict: Dictionary with keys: opportunity_id, primary_dex, counter_dex,
                        borrow_amount, collateral_required, expected_profit,
                        expiry_timestamp, chain_id

        Returns:
            ABI-encoded bytes ready for Keccak-256 hashing

        Raises:
            EncodingError: If encoding fails or required fields are missing
        """
        try:
            # Extract and validate fields
            opportunity_id = signal_dict.get("opportunity_id", "")
            primary_dex = signal_dict.get("primary_dex", "0x0000000000000000000000000000000000000000")
            counter_dex = signal_dict.get("counter_dex", "0x0000000000000000000000000000000000000000")
            borrow_amount = signal_dict.get("borrow_amount", 0)
            collateral_required = signal_dict.get("collateral_required", 0)
            expected_profit = signal_dict.get("expected_profit_usdc", signal_dict.get("expected_profit", 0))
            expiry_timestamp = signal_dict.get("expiry_timestamp", 0)
            chain_id = signal_dict.get("chain_id", 0)

            # Convert opportunity_id to bytes32
            opportunity_id_bytes = SignalEncoder._to_bytes32(opportunity_id)

            # Convert amounts to micro-units (multiply by 10^6 for USDC)
            borrow_amount_int = SignalEncoder._to_uint256(borrow_amount)
            collateral_int = SignalEncoder._to_uint256(collateral_required)
            profit_int = SignalEncoder._to_uint256(expected_profit)

            # Convert timestamps and chain_id to integers
            expiry_timestamp_int = int(expiry_timestamp)
            chain_id_int = int(chain_id)

            # Validate addresses
            if not isinstance(primary_dex, str):
                primary_dex = str(primary_dex)
            if not isinstance(counter_dex, str):
                counter_dex = str(counter_dex)

            # Encode using eth_abi.encode()
            encoded = eth_abi_encode(
                SignalEncoder.CANONICAL_TYPES,
                [
                    opportunity_id_bytes,
                    primary_dex,
                    counter_dex,
                    borrow_amount_int,
                    collateral_int,
                    profit_int,
                    expiry_timestamp_int,
                    chain_id_int,
                ],
            )

            return encoded

        except Exception as e:
            raise EncodingError(f"Failed to encode signal: {e}") from e

    @staticmethod
    def encode_for_signing_with_hash(signal_dict: Dict[str, Any]) -> Tuple[bytes, bytes]:
        """
        Encode a signal and return both the encoded bytes and the Keccak-256 hash.

        Args:
            signal_dict: Dictionary with signal fields

        Returns:
            Tuple of (encoded_bytes, keccak256_hash)

        Raises:
            EncodingError: If encoding fails
        """
        encoded = SignalEncoder.encode_for_signing(signal_dict)
        msg_hash = keccak(encoded)
        return encoded, msg_hash

    @staticmethod
    def compute_output_hash(output_dict: Dict[str, Any]) -> str:
        """
        Compute the canonical SHA-256 output hash used in verification.

        Args:
            output_dict: Dictionary containing decision, expected_profit_usdc,
                         risk_score, and expiry_timestamp.

        Returns:
            Hex-encoded SHA-256 hash string with 0x prefix.
        """
        import json as _json
        import hashlib as _hashlib

        canonical = {
            "decision": output_dict.get("decision", ""),
            "expected_profit": str(output_dict.get("expected_profit_usdc", output_dict.get("expected_profit", 0))),
            "risk_score": round(float(output_dict.get("risk_score", 0.0)), 8),
            "expiry_timestamp": int(output_dict.get("expiry_timestamp", 0)),
        }
        canonical_json = _json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return "0x" + _hashlib.sha256(canonical_json.encode()).hexdigest()

    @staticmethod
    def decode_from_bytes(encoded: bytes) -> Dict[str, Any]:
        """
        Decode canonical ABI-encoded bytes back into a signal dictionary.

        This is the reverse of encode_for_signing(). Used for verification and auditing.

        Args:
            encoded: ABI-encoded bytes from encode_for_signing()

        Returns:
            Dictionary with decoded signal fields

        Raises:
            EncodingError: If decoding fails
        """
        try:
            # Decode using eth_abi
            from eth_abi import decode as eth_abi_decode

            decoded_values = eth_abi_decode(
                SignalEncoder.CANONICAL_TYPES,
                encoded,
            )

            return {
                "opportunity_id": ("0x" + decoded_values[0].hex()) if isinstance(decoded_values[0], bytes) else str(decoded_values[0]),
                "primary_dex": decoded_values[1],
                "counter_dex": decoded_values[2],
                "borrow_amount": SignalEncoder._from_uint256(decoded_values[3]),
                "collateral_required": SignalEncoder._from_uint256(decoded_values[4]),
                "expected_profit_usdc": SignalEncoder._from_uint256(decoded_values[5]),
                "expiry_timestamp": int(decoded_values[6]),
                "chain_id": int(decoded_values[7]),
            }

        except Exception as e:
            raise EncodingError(f"Failed to decode bytes: {e}") from e

    @staticmethod
    def verify_roundtrip(original_dict: Dict[str, Any]) -> bool:
        """
        Verify that encoding and decoding are consistent (round-trip test).

        Args:
            original_dict: Original signal dictionary

        Returns:
            True if round-trip succeeds (encode -> decode -> original fields match)

        Raises:
            EncodingError: If round-trip fails
        """
        try:
            encoded = SignalEncoder.encode_for_signing(original_dict)
            decoded = SignalEncoder.decode_from_bytes(encoded)

            # Compare key fields (allowing small floating-point differences)
            for key in ["opportunity_id", "primary_dex", "counter_dex", "expiry_timestamp", "chain_id"]:
                if key in original_dict and key in decoded:
                    if str(original_dict[key]).lower() != str(decoded[key]).lower():
                        return False

            # For amounts, allow small rounding differences due to Decimal -> int conversion
            for key in ["borrow_amount", "collateral_required", "expected_profit_usdc"]:
                if key in original_dict and key in decoded:
                    orig_val = Decimal(str(original_dict.get(key, original_dict.get(key.replace("_usdc", ""), 0))))
                    decoded_val = Decimal(str(decoded[key]))
                    if abs(orig_val - decoded_val) > Decimal("0.01"):
                        return False

            return True

        except Exception as e:
            raise EncodingError(f"Round-trip verification failed: {e}") from e

    @staticmethod
    def _to_bytes32(value: Any) -> bytes:
        """
        Convert a value to a 32-byte (bytes32) representation.

        Args:
            value: String, hex string, bytes, or integer

        Returns:
            32-byte value (zero-padded if necessary)
        """
        if isinstance(value, bytes):
            # Already bytes, pad to 32
            if len(value) < 32:
                return value.ljust(32, b"\x00")
            elif len(value) > 32:
                return value[:32]
            return value

        elif isinstance(value, str):
            # Hex string or regular string
            if value.startswith("0x"):
                # Hex string
                hex_str = value[2:]
                value_bytes = bytes.fromhex(hex_str)
            else:
                # Regular string
                value_bytes = value.encode()

            # Pad to 32 bytes
            if len(value_bytes) < 32:
                return value_bytes.ljust(32, b"\x00")
            elif len(value_bytes) > 32:
                return value_bytes[:32]
            return value_bytes

        elif isinstance(value, int):
            # Integer, convert to bytes
            value_bytes = value.to_bytes(32, byteorder="big")
            return value_bytes

        else:
            # Fallback: convert to string
            return SignalEncoder._to_bytes32(str(value))

    @staticmethod
    def _to_uint256(value: Any) -> int:
        """
        Convert a value to a uint256 (256-bit unsigned integer).

        Multiplies by 10^6 to account for USDC's 6 decimal places.

        Args:
            value: Decimal, float, string, or integer

        Returns:
            Integer in micro-units (amount * 10^6)
        """
        try:
            if isinstance(value, (int, float)):
                value = Decimal(str(value))
            elif isinstance(value, str):
                value = Decimal(value)
            elif not isinstance(value, Decimal):
                value = Decimal(str(value))

            # Multiply by 10^6 for USDC
            micro_units = value * Decimal("1000000")

            # Convert to integer
            return int(micro_units.to_integral_value())

        except Exception as e:
            raise EncodingError(f"Failed to convert {value} to uint256: {e}") from e

    @staticmethod
    def _from_uint256(micro_units: int) -> Decimal:
        """
        Convert from micro-units back to decimal representation.

        Args:
            micro_units: Amount in micro-units (amount * 10^6)

        Returns:
            Decimal representation (divided by 10^6)
        """
        return Decimal(micro_units) / Decimal("1000000")
