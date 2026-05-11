import os
from json import dumps
from typing import Any

# Note: Full SGX attestation parsing is complex and provider-specific.
# This module provides a minimal interface and hooks to integrate with
# Intel IAS or 0G attestation verification services.

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


DEFAULT_LOCAL_SIGNING_KEY = os.getenv(
    "TEE_LOCAL_SIGNING_PRIVATE_KEY",
    "0x59c6995e998f97a5a004497e5da6f7a5fba8f3a15d7f66b5a6a51f6c4a1b0d1d",
)

class AttestationVerifier:
    def __init__(self, cert_path: str = None):
        self.cert_path = cert_path or os.getenv("TEE_ATTESTATION_CERT_PATH")
        # load known-good enclave measurement if available
        self.known_mrenclave = os.getenv("TEE_KNOWN_MRENCLAVE")
        self.expected_signer = os.getenv("TEE_SIGNER_ADDRESS") or Account.from_key(DEFAULT_LOCAL_SIGNING_KEY).address

    def verify_quote(self, attestation_quote: bytes) -> bool:
        # Placeholder: in production parse quote and verify with IAS/0G
        if not attestation_quote or not self.cert_path or not os.path.exists(self.cert_path):
            return False
        return len(attestation_quote) > 0

    def verify_response_signature(self, response: Any, expected_pubkey_hex: str = None) -> bool:
        # response must include the signed signal and all fields used to derive it
        try:
            if isinstance(response, dict):
                data = response
            else:
                data = {
                    "opportunity_id": getattr(response, "opportunity_id", None),
                    "decision": getattr(response, "decision", None),
                    "expected_profit_usdc": str(getattr(response, "expected_profit_usdc", None)),
                    "risk_score": round(float(getattr(response, "risk_score", 0.0)), 8),
                    "confidence": round(float(getattr(response, "confidence", 0.0)), 8),
                    "reasoning_summary": getattr(response, "reasoning_summary", None),
                    "signal_hash": getattr(response, "signal_hash", None),
                    "tee_signature": getattr(response, "tee_signature", None),
                }

            sig_hex = data.get("tee_signature")
            signal_hash = data.get("signal_hash")
            if not sig_hex or not signal_hash:
                return False

            canonical_payload = dumps(
                {
                    "opportunity_id": data.get("opportunity_id"),
                    "decision": data.get("decision"),
                    "expected_profit_usdc": str(data.get("expected_profit_usdc")),
                    "risk_score": round(float(data.get("risk_score", 0.0)), 8),
                    "confidence": round(float(data.get("confidence", 0.0)), 8),
                    "reasoning_summary": data.get("reasoning_summary"),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            expected_hash = Web3.to_hex(Web3.keccak(text=canonical_payload))
            if expected_hash.lower() != str(signal_hash).lower():
                return False

            recovered = Account.recover_message(encode_defunct(text=str(signal_hash)), signature=sig_hex)
            expected_address = expected_pubkey_hex or self.expected_signer
            return recovered.lower() == str(expected_address).lower()
        except Exception:
            return False

    def refresh_attestation(self):
        # placeholder to re-fetch provider attestation certs
        # real implementation should call 0G attestation endpoints or IAS
        if self.cert_path and os.path.exists(self.cert_path):
            return True
        return False
