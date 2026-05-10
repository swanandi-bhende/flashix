import os
import asyncio
import time
import pytest
from decimal import Decimal

from compute.payload_schema import InferenceRequest, InferenceResponse
from compute.arbitrage_analyzer import ArbitrageAnalyzer
from compute.attestation_verifier import AttestationVerifier

@pytest.mark.asyncio
async def test_determinism():
    os.environ["TEE_MODE"] = "local"
    analyzer = ArbitrageAnalyzer()
    now = int(time.time())
    payload = {
        "opportunity_id": "uuid-1234-5678-9012",
        "dex_a": "0x0000000000000000000000000000000000000001",
        "dex_b": "0x0000000000000000000000000000000000000002",
        "price_a": Decimal("100.0"),
        "price_b": Decimal("101.0"),
        "borrow_amount_usdc": Decimal("10000"),
        "funding_rate_a": Decimal("0.001"),
        "funding_rate_b": Decimal("0.0"),
        "timestamp": now,
        "chain_id": 16600,
    }
    req = InferenceRequest.model_validate(payload)
    outs = [analyzer.analyze(req).model_dump() for _ in range(10)]
    first = outs[0]
    for o in outs:
        assert o == first

def test_invalid_payload_rejected():
    now = int(time.time())
    bads = [
        {"opportunity_id":"x","dex_a":"0x1","dex_b":"0x2","price_a":-1,"price_b":100,"borrow_amount_usdc":5,"funding_rate_a":0,"funding_rate_b":0,"timestamp":now,"chain_id":16600},
        {"opportunity_id":"x","dex_a":"0x0000000000000000000000000000000000000001","dex_b":"0x0000000000000000000000000000000000000001","price_a":100,"price_b":100,"borrow_amount_usdc":100,"funding_rate_a":0,"funding_rate_b":0,"timestamp":now,"chain_id":16600},
    ]
    for b in bads:
        with pytest.raises(Exception):
            InferenceRequest.model_validate(b)

def test_signal_verification():
    # This is a lightweight test that ensures the verifier API works in local mode
    av = AttestationVerifier(cert_path=None)
    resp = {"signal_hash": "deadbeef", "tee_signature": "0x"}
    # should return False for invalid signature
    assert av.verify_response_signature(resp) is False
