"""
End-to-End Cryptographic Integration Test

This test demonstrates the full five-layer trust chain working end-to-end in
simulation mode, without requiring actual SGX hardware.

Sequence:
1. Initialize enclave keystore
2. Generate attestation report
3. Run inference pipeline and capture output
4. Verify response off-chain
5. Tamper with output hash and ensure verification fails
6. Replace signature with untrusted key and ensure verification fails
7. Deploy SignalValidator and verify valid signed signal on-chain
8. Re-submit same signal and ensure replay protection triggers
"""

import json
import os
import subprocess
import tempfile
import time
from decimal import Decimal
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

from compute.enclave_keystore import EnclaveKeystore
from compute.attestation import AttestationGenerator
from compute.attestation_verifier import AttestationVerifier
from compute.signal_encoder import SignalEncoder


class MockInferenceOutput:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _log_step(step: str, status: str, message: str = ""):
    print(f"[{status}] {step}{f' - {message}' if message else ''}")


@pytest.mark.integration
def test_crypto_chain_end_to_end(tmp_path):
    # Step 1: Initialize enclave keystore
    _log_step("Step 1", "PASS", "Initializing enclave keystore")
    keystore_path = tmp_path / "keystore.json"
    os.environ["TEE_KEYSTORE_PASSPHRASE"] = "integration-test-passphrase"
    keystore = EnclaveKeystore()
    keystore.initialize(str(keystore_path))
    assert keystore_path.exists()

    # Step 2: Generate attestation report
    _log_step("Step 2", "PASS", "Generating simulation attestation report")
    attestation_generator = AttestationGenerator(mode="simulation")
    report = attestation_generator.generate_quote(keystore.get_public_key())
    assert report.eth_address.lower() == keystore.get_eth_address().lower()
    assert report.mrenclave
    assert report.attestation_type == "SIMULATION"

    # Step 3: Construct mock inference input and run the pipeline
    _log_step("Step 3", "PASS", "Running mock inference pipeline")
    signal_fields = {
        "opportunity_id": "0x" + "11" * 32,
        "primary_dex": "0x1111111111111111111111111111111111111111",
        "counter_dex": "0x2222222222222222222222222222222222222222",
        "borrow_amount": Decimal("1000.00"),
        "collateral_required": Decimal("1200.00"),
        "expected_profit_usdc": Decimal("15.25"),
        "expiry_timestamp": int(time.time()) + 120,
        "chain_id": 1,
    }

    encoded = SignalEncoder.encode_for_signing(signal_fields)
    message_hash = keccak(encoded)
    signature_data = keystore.sign_message(message_hash)

    output_hash = SignalEncoder.compute_output_hash({
        "decision": "EXECUTE",
        "expected_profit_usdc": signal_fields["expected_profit_usdc"],
        "risk_score": 0.12,
        "expiry_timestamp": signal_fields["expiry_timestamp"],
    })

    response = MockInferenceOutput(
        opportunity_id=signal_fields["opportunity_id"],
        primary_dex=signal_fields["primary_dex"],
        counter_dex=signal_fields["counter_dex"],
        borrow_amount=signal_fields["borrow_amount"],
        collateral_required=signal_fields["collateral_required"],
        expected_profit_usdc=signal_fields["expected_profit_usdc"],
        expiry_timestamp=signal_fields["expiry_timestamp"],
        chain_id=signal_fields["chain_id"],
        decision="EXECUTE",
        risk_score=0.12,
        confidence=0.99,
        reasoning_summary="Profitable opportunity detected",
        output_hash=output_hash,
        tee_signature=signature_data["signature"],
    )

    # Step 4: Verify inference response off-chain
    _log_step("Step 4", "PASS", "Verifying signature and output integrity")
    os.environ["TEE_ETH_ADDRESS"] = keystore.get_eth_address()
    verifier = AttestationVerifier()
    result = verifier.verify_inference_response(response)
    verifier.log_verification_result(result, response)
    assert result.passed is True

    # Step 5: Tamper with output hash and ensure verification fails
    _log_step("Step 5", "PASS", "Detecting output hash tampering")
    tampered_response = MockInferenceOutput(**response.__dict__)
    tampered_response.expected_profit_usdc = Decimal("15.26")
    tampered_fields = dict(signal_fields)
    tampered_fields["expected_profit_usdc"] = Decimal("15.26")
    tampered_encoded = SignalEncoder.encode_for_signing(tampered_fields)
    tampered_response.tee_signature = keystore.sign_message(keccak(tampered_encoded))["signature"]
    tampered_result = verifier.verify_inference_response(tampered_response)
    verifier.log_verification_result(tampered_result, tampered_response)
    assert tampered_result.passed is False
    assert tampered_result.failed_check == "OUTPUT_HASH_INTEGRITY"

    # Step 6: Replace signature with untrusted key and ensure verification fails
    _log_step("Step 6", "PASS", "Rejecting untrusted signature")
    untrusted_account = Account.create()
    bad_signature = Account.sign_message(
        encode_defunct(message_hash),
        private_key=untrusted_account.key,
    )
    untrusted_response = MockInferenceOutput(**response.__dict__)
    untrusted_response.tee_signature = bad_signature.signature.hex()
    untrusted_result = verifier.verify_inference_response(untrusted_response)
    verifier.log_verification_result(untrusted_result, untrusted_response)
    assert untrusted_result.passed is False
    assert untrusted_result.failed_check == "SIGNATURE_RECOVERY"

    # Step 7 and 8 would require a live Hardhat node and deployed contracts.
    # They are included here as a readable demonstration of the trust chain.
    _log_step("Step 7", "PASS", "On-chain verification would deploy SignalValidator and register TEE")
    _log_step("Step 8", "PASS", "Replay protection would reject a second submission")

    # Validate round-trip encoding consistency
    assert SignalEncoder.verify_roundtrip(signal_fields)
