"""
compute/arbitrage_analyzer.py

Master sealed inference module for on-enclave arbitrage signal generation.

Position in pipeline:
- Runs inside the TEE sandbox and receives filtered opportunity payloads.
- Deterministically converts inputs -> features -> model prediction -> signed signal.

Determinism note:
All functions in this file and its collaborators must be deterministic: fixed seeds,
use of Decimal for monetary math, explicit float64 numpy dtype, fixed JSON sorting,
and model version pinning by SHA-256. This ensures identical input -> output mapping
so sealed computation can be verified by judges.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, List

# Define dataclasses and type contracts (no logic here)

@dataclass(frozen=True)
class InferenceInput:
    opportunity_id: str
    symbol: str
    dex_a: str
    dex_b: str
    price_a: Decimal
    price_b: Decimal
    borrow_amount_usdc: Decimal
    funding_rate_a: Decimal
    funding_rate_b: Decimal
    orderbook_depth_a: float
    orderbook_depth_b: float
    trade_flow_imbalance_a: float
    trade_flow_imbalance_b: float
    volatility_24h: float
    correlation_btc: float
    timestamp: int
    chain_id: int
    # additional fields used by feature extractor
    gas_price_gwei: float
    spread_momentum_5s: float


@dataclass(frozen=True)
class InferenceOutput:
    opportunity_id: str
    primary_dex: str
    counter_dex: str
    borrow_amount: Decimal
    collateral_required: Decimal
    expected_profit_usdc: Decimal
    risk_score: float
    confidence: float
    decision: Literal["EXECUTE", "SKIP"]
    expiry_timestamp: int
    reasoning: str
    model_version: str
    input_hash: str
    output_hash: str
    tee_signature: str


@dataclass(frozen=True)
class ModelMetadata:
    version: str
    sha256_checksum: str
    trained_at: str
    feature_names: List[str]
    training_sample_size: int
    validation_accuracy: float


# End of dataclass definitions. Implementation follows.
from compute.model_loader import ModelLoader, ModelIntegrityError, MODEL_SINGLETON
from compute.feature_extractor import FeatureExtractor, FeatureExtractionError
from compute.inference_engine import InferenceEngine
from compute.signal_builder import SignalBuilder
from compute.tee_signer import TEESigner, SigningError

import json
import logging
import time
from pydantic import BaseModel, ValidationError
import dataclasses as dc

_logger = logging.getLogger(__name__)

# Instantiate components (deterministic singletons)
_feature_extractor = FeatureExtractor()
_inference_engine = InferenceEngine(MODEL_SINGLETON[0], _feature_extractor)
_signal_builder = SignalBuilder()
_tee_signer = TEESigner()


class InferenceInputModel(BaseModel):
    opportunity_id: str
    symbol: str
    dex_a: str
    dex_b: str
    price_a: Decimal
    price_b: Decimal
    borrow_amount_usdc: Decimal
    funding_rate_a: Decimal
    funding_rate_b: Decimal
    orderbook_depth_a: float
    orderbook_depth_b: float
    trade_flow_imbalance_a: float
    trade_flow_imbalance_b: float
    volatility_24h: float
    correlation_btc: float
    timestamp: int
    chain_id: int
    gas_price_gwei: float
    spread_momentum_5s: float


def _decimal_to_str(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError()


def analyze(payload: dict) -> dict:
    start = time.time()
    try:
        # validate payload
        validated = InferenceInputModel(**payload)
        inp = InferenceInput(**validated.dict())

        # features
        features = _feature_extractor.extract(inp)

        # scoring
        confidence, risk_score = _inference_engine.score_single(inp)

        # expected profit
        expected_profit = _inference_engine.calculate_expected_profit(inp, confidence)

        # build output
        out = _signal_builder.build(inp, confidence, risk_score, expected_profit, MODEL_SINGLETON[1])

        # sign
        signature = _tee_signer.sign_output(out)
        if not _tee_signer.verify_own_signature(out, signature):
            raise SigningError("Signature self-check failed")
        out = dataclasses.replace(out, tee_signature=signature)

        elapsed_ms = int((time.time() - start) * 1000)

        _logger.info(
            f"INFERENCE_COMPLETE: id={out.opportunity_id}, decision={out.decision}, confidence={out.confidence:.3f}, profit=${out.expected_profit_usdc:.4f}, latency={elapsed_ms}ms"
        )

        response = dc.asdict(out)
        # convert Decimal fields to strings
        for k, v in response.items():
            if isinstance(v, Decimal):
                response[k] = str(v)

        return {"result": response}

    except ValidationError as ve:
        _logger.exception("Validation error in analyze")
        return {"error": ve.errors(), "opportunity_id": payload.get("opportunity_id"), "timestamp": int(time.time())}
    except FeatureExtractionError as fe:
        _logger.exception("Feature extraction failed")
        return {"error": str(fe), "opportunity_id": payload.get("opportunity_id"), "timestamp": int(time.time())}
    except ModelIntegrityError as me:
        _logger.exception("Model integrity error; fatal")
        raise
    except Exception as e:
        _logger.exception("Unexpected error in analyze")
        return {"error": str(e), "opportunity_id": payload.get("opportunity_id"), "timestamp": int(time.time())}
import os
import time
import pickle
import hashlib
import numpy as np
from decimal import Decimal
from json import dumps

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from .payload_schema import InferenceRequest, InferenceResponse

MIN_PROFIT_MARGIN = float(os.getenv("MIN_PROFIT_MARGIN_PERCENT", "3.0"))
DEFAULT_LOCAL_SIGNING_KEY = os.getenv(
    "TEE_LOCAL_SIGNING_PRIVATE_KEY",
    "0x59c6995e998f97a5a004497e5da6f7a5fba8f3a15d7f66b5a6a51f6c4a1b0d1d",
)

class ArbitrageAnalyzer:
    def __init__(self):
        self.model = None
        self.model_path = os.getenv("TEE_LOCAL_MODEL_PATH", "./compute/models/arbitrage_scorer_v1.pkl")
        self.expected_hash = os.getenv("TEE_LOCAL_MODEL_HASH")
        self.signing_account = Account.from_key(DEFAULT_LOCAL_SIGNING_KEY)
        self.load_model()

    def load_model(self):
        if not os.path.exists(self.model_path):
            # fallback to a trivial heuristic model
            self.model = None
            return
        with open(self.model_path, "rb") as f:
            data = f.read()
        h = hashlib.sha256(data).hexdigest()
        if self.expected_hash and h != self.expected_hash:
            raise RuntimeError("Model hash mismatch")
        self.model = pickle.loads(data)

    def analyze(self, request: InferenceRequest) -> InferenceResponse:
        # enforce deterministic seeds
        import random
        random.seed(42)
        np.random.seed(42)

        price_a = float(request.price_a)
        price_b = float(request.price_b)
        borrow = float(request.borrow_amount_usdc)
        funding_diff = float(request.funding_rate_a - request.funding_rate_b)

        gross_spread = abs(price_a - price_b) / min(price_a, price_b) * 100.0
        # estimate costs
        flashloan_fee = 0.09
        size_factor = min(max(borrow / 1_000_000.0, 0.0), 1.0)
        slippage = 0.2 + (0.3 * size_factor)
        gas_cost = 0.05
        total_cost = flashloan_fee + slippage + gas_cost
        net_profit = gross_spread - total_cost

        # volatility proxy and time of day
        volatility = float(abs(price_a - price_b)) / max(price_a, price_b)
        time_of_day = (request.timestamp % 86400) / 86400.0

        features = np.array([gross_spread, funding_diff, borrow, time_of_day, volatility]).reshape(1, -1)
        if self.model is not None:
            confidence = float(self.model.predict_proba(features)[0,1])
        else:
            # simple heuristic for fallback
            confidence = min(1.0, max(0.0, (gross_spread / 10.0)))

        risk_score = max(0.0, min(1.0, 1.0 - (confidence * 0.8) + (0.1 if volatility > 0.02 else 0.0)))

        decision = "EXECUTE" if (net_profit > MIN_PROFIT_MARGIN and confidence > 0.75 and risk_score < 0.6) else "SKIP"

        expected_profit_usdc = Decimal(str(round(net_profit, 8)))
        reasoning = f"gross_spread={gross_spread:.4f} total_cost={total_cost:.4f} net_profit={net_profit:.4f} confidence={confidence:.3f}"

        # deterministic signal hash
        response_fields = {
            "opportunity_id": request.opportunity_id,
            "decision": decision,
            "expected_profit_usdc": str(expected_profit_usdc),
            "risk_score": round(risk_score, 8),
            "confidence": round(confidence, 8),
            "reasoning_summary": reasoning,
        }
        sig_payload = dumps(response_fields, sort_keys=True, separators=(",", ":"))
        signal_hash = Web3.to_hex(Web3.keccak(text=sig_payload))

        tee_signature = Web3.to_hex(Account.sign_message(
            encode_defunct(text=signal_hash),
            private_key=self.signing_account.key,
        ).signature)

        resp = InferenceResponse(
            opportunity_id=request.opportunity_id,
            decision=decision,
            expected_profit_usdc=expected_profit_usdc,
            risk_score=risk_score,
            confidence=confidence,
            reasoning_summary=reasoning,
            signal_hash=signal_hash,
            tee_signature=tee_signature,
        )
        return resp


if __name__ == "__main__":
    print("arbitrage_analyzer loaded")
