import os
import asyncio
import time
import pytest
from decimal import Decimal
from uuid import uuid4

from compute.payload_schema import InferenceRequest, InferenceResponse
from compute.arbitrage_analyzer import ArbitrageAnalyzer
from compute.attestation_verifier import AttestationVerifier

@pytest.mark.asyncio
async def test_determinism():
    os.environ["TEE_MODE"] = "local"
    analyzer = ArbitrageAnalyzer()
    now = int(time.time())
    payload = {
        "opportunity_id": str(uuid4()),
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

def test_latency_budget():
    os.environ["TEE_MODE"] = "local"
    analyzer = ArbitrageAnalyzer()
    now = int(time.time())
    payload = {
        "opportunity_id": str(uuid4()),
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
    samples = []
    for _ in range(50):
        start = time.perf_counter()
        analyzer.analyze(req)
        samples.append((time.perf_counter() - start) * 1000)
    ordered = sorted(samples)
    p95 = ordered[int(round((len(ordered) - 1) * 0.95))]
    assert p95 < 1000

def test_invalid_payload_rejected():
    now = int(time.time())
    bads = [
        {"opportunity_id": "not-a-uuid", "dex_a": "0x1", "dex_b": "0x2", "price_a": -1, "price_b": 100, "borrow_amount_usdc": 5, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000001", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 9, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 1_000_001, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 1.5, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 0, "funding_rate_b": -1.5, "timestamp": now, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now + 60, "chain_id": 16600},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 1},
        {"opportunity_id": str(uuid4()), "dex_a": "0x0000000000000000000000000000000000000001", "dex_b": "0x0000000000000000000000000000000000000002", "price_a": 100.123456789, "price_b": 100, "borrow_amount_usdc": 100, "funding_rate_a": 0, "funding_rate_b": 0, "timestamp": now, "chain_id": 16600},
    ]
    for b in bads:
        with pytest.raises(Exception):
            InferenceRequest.model_validate(b)

def test_signal_verification():
    analyzer = ArbitrageAnalyzer()
    verifier = AttestationVerifier(cert_path=None)
    now = int(time.time())
    req = InferenceRequest.model_validate({
        "opportunity_id": str(uuid4()),
        "dex_a": "0x0000000000000000000000000000000000000001",
        "dex_b": "0x0000000000000000000000000000000000000002",
        "price_a": Decimal("100.0"),
        "price_b": Decimal("102.0"),
        "borrow_amount_usdc": Decimal("10000"),
        "funding_rate_a": Decimal("0.001"),
        "funding_rate_b": Decimal("0.0"),
        "timestamp": now,
        "chain_id": 16600,
    })
    response = analyzer.analyze(req).model_dump()
    assert verifier.verify_response_signature(response) is True
    tampered = dict(response)
    tampered["confidence"] = min(1.0, float(tampered["confidence"]) + 0.01)
    assert verifier.verify_response_signature(tampered) is False
