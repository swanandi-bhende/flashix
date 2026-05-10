import os
import time
import pickle
import hashlib
import numpy as np
from decimal import Decimal

from .payload_schema import InferenceRequest, InferenceResponse

MIN_PROFIT_MARGIN = float(os.getenv("MIN_PROFIT_MARGIN_PERCENT", "3.0"))

class ArbitrageAnalyzer:
    def __init__(self):
        self.model = None
        self.model_path = os.getenv("TEE_LOCAL_MODEL_PATH", "./compute/models/arbitrage_scorer_v1.pkl")
        self.expected_hash = os.getenv("TEE_LOCAL_MODEL_HASH")
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
        flashloan_fee = 0.0009 * 100.0  # 0.09% in percent
        slippage = 0.35  # percent (estimate)
        total_cost = flashloan_fee + slippage
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

        risk_score = max(0.0, min(1.0, 1.0 - (confidence * 0.8)))

        decision = "EXECUTE" if (net_profit > MIN_PROFIT_MARGIN and confidence > 0.75 and risk_score < 0.6) else "SKIP"

        expected_profit_usdc = Decimal(str(net_profit))
        reasoning = f"gross_spread={gross_spread:.4f} total_cost={total_cost:.4f} net_profit={net_profit:.4f} confidence={confidence:.3f}"

        # deterministic signal hash
        sig_payload = f"{request.opportunity_id}|{decision}|{expected_profit_usdc}|{risk_score:.4f}|{confidence:.4f}"
        try:
            signal_hash = hashlib.new('keccak256', sig_payload.encode()).hexdigest()
        except Exception:
            signal_hash = hashlib.sha256(sig_payload.encode()).hexdigest()

        # tee_signature is produced by the enclave; in local mode we leave a placeholder
        tee_signature = os.getenv("TEE_LOCAL_SIGNATURE_PLACEHOLDER", "0x00")

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
