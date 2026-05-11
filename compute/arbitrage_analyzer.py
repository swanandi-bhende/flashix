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
