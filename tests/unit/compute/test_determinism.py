import os
import importlib
import hashlib
import json
from decimal import Decimal
import tempfile
import shutil

import pytest
import dataclasses

from compute.model_training import train_arbitrage_scorer


def setup_module(module):
    # deterministic tee key from sha256 of known seed
    key = hashlib.sha256(b"test-tee-key").hexdigest()
    os.environ["TEE_SIGNING_KEY"] = key
    # ensure model exists
    train_arbitrage_scorer.main()


def test_single_inference_determinism():
    importlib.reload(importlib.import_module("compute.model_loader"))
    analyzer = importlib.import_module("compute.arbitrage_analyzer")

    payload = {
        "opportunity_id": "op-123",
        "symbol": "BTC-PERP",
        "dex_a": "dexA",
        "dex_b": "dexB",
        "price_a": "50000",
        "price_b": "49000",
        "borrow_amount_usdc": "10000",
        "funding_rate_a": "0.0001",
        "funding_rate_b": "0.00005",
        "orderbook_depth_a": 100.0,
        "orderbook_depth_b": 80.0,
        "trade_flow_imbalance_a": 0.1,
        "trade_flow_imbalance_b": -0.05,
        "volatility_24h": 0.5,
        "correlation_btc": 0.2,
        "timestamp": 1620000000,
        "chain_id": 1337,
        "gas_price_gwei": 50.0,
        "spread_momentum_5s": 0.01,
    }

    outputs = []
    for _ in range(100):
        r = analyzer.analyze(payload)
        assert "result" in r
        outputs.append(r["result"])

    first = outputs[0]
    for o in outputs[1:]:
        assert o["output_hash"] == first["output_hash"]
        assert o["decision"] == first["decision"]
        assert o["expected_profit_usdc"] == first["expected_profit_usdc"]
        assert float(o["risk_score"]) == float(first["risk_score"])
        assert float(o["confidence"]) == float(first["confidence"])
        assert o["tee_signature"] == first["tee_signature"]


def test_model_checksum_validation():
    # Test that corrupted model checksum is caught
    import compute.model_loader as ml
    import tempfile
    import shutil
    
    # __file__ is at tests/unit/compute/test_determinism.py, go up 4 to get to repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    model_dir = os.path.join(repo_root, "models")
    pkl = os.path.join(model_dir, "arbitrage_scorer_v1.pkl")
    meta = os.path.join(model_dir, "arbitrage_scorer_v1_metadata.json")
    
    # Create temp directory with corrupted model
    with tempfile.TemporaryDirectory() as tmpdir:
        # copy files to temp
        shutil.copy(pkl, tmpdir)
        shutil.copy(meta, tmpdir)
        
        # corrupt the pkl file
        temp_pkl = os.path.join(tmpdir, "arbitrage_scorer_v1.pkl")
        with open(temp_pkl, "rb") as fh:
            data = bytearray(fh.read())
        data[0] = (data[0] + 1) % 256
        with open(temp_pkl, "wb") as fh:
            fh.write(data)
        
        # now loader should fail
        t = ml.ModelLoader(tmpdir)
        with pytest.raises(ml.ModelIntegrityError):
            t.load()


def test_feature_extraction_precision():
    importlib.reload(importlib.import_module("compute.feature_extractor"))
    fe = importlib.import_module("compute.feature_extractor").FeatureExtractor()
    from compute.arbitrage_analyzer import InferenceInput

    inp = InferenceInput(
        opportunity_id="x",
        symbol="s",
        dex_a="a",
        dex_b="b",
        price_a=Decimal("100.0"),
        price_b=Decimal("90.0"),
        borrow_amount_usdc=Decimal("1000"),
        funding_rate_a=Decimal("0.001"),
        funding_rate_b=Decimal("0.0005"),
        orderbook_depth_a=100.0,
        orderbook_depth_b=50.0,
        trade_flow_imbalance_a=0.1,
        trade_flow_imbalance_b=0.05,
        volatility_24h=0.2,
        correlation_btc=0.5,
        timestamp=1620000000,
        chain_id=1,
        gas_price_gwei=50.0,
        spread_momentum_5s=0.01,
    )

    vec = fe.extract(inp)
    assert vec.shape == (12,)
    assert round(float(vec[0]), 10) == round(abs(100.0 - 90.0) / 90.0 * 100.0, 10)


def test_signing_verification_roundtrip():
    importlib.reload(importlib.import_module("compute.signal_builder"))
    importlib.reload(importlib.import_module("compute.tee_signer"))
    sb = importlib.import_module("compute.signal_builder").SignalBuilder()
    signer = importlib.import_module("compute.tee_signer").TEESigner()
    from compute.arbitrage_analyzer import InferenceInput

    inp = InferenceInput(
        opportunity_id="op-x",
        symbol="SYM",
        dex_a="A",
        dex_b="B",
        price_a=Decimal("100"),
        price_b=Decimal("99"),
        borrow_amount_usdc=Decimal("500"),
        funding_rate_a=Decimal("0"),
        funding_rate_b=Decimal("0"),
        orderbook_depth_a=10.0,
        orderbook_depth_b=10.0,
        trade_flow_imbalance_a=0.0,
        trade_flow_imbalance_b=0.0,
        volatility_24h=0.1,
        correlation_btc=0.0,
        timestamp=1620000000,
        chain_id=1,
        gas_price_gwei=10.0,
        spread_momentum_5s=0.0,
    )

    import compute.model_loader as ml
    model_meta = ml.MODEL_SINGLETON[1]
    out = sb.build(inp, 0.9, 0.1, Decimal("5.0"), model_meta)
    sig = signer.sign_output(out)
    assert signer.verify_own_signature(out, sig)

    # tamper
    out_dict = dataclasses.asdict(out)
    out_dict["expected_profit_usdc"] = Decimal("6.0")
    from compute.arbitrage_analyzer import InferenceOutput
    out_tampered = InferenceOutput(**out_dict)
    assert not signer.verify_own_signature(out_tampered, sig)
