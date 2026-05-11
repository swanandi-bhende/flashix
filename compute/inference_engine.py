from decimal import Decimal
from typing import List, Tuple
import os

MAX_CONCURRENT_POSITIONS = int(os.environ.get("MAX_CONCURRENT_POSITIONS", "1"))


class InferenceEngine:
    def __init__(self, model, feature_extractor):
        self.model = model
        self.feature_extractor = feature_extractor

    def score_single(self, input) -> Tuple[float, float]:
        features = self.feature_extractor.extract(input)
        probs = self.model.predict_proba(features.reshape(1, -1))[0]
        # probs -> [prob_unprofitable, prob_profitable]
        prob_profitable = float(probs[-1])
        confidence = prob_profitable
        risk_score = 1.0 - prob_profitable
        return confidence, risk_score

    def calculate_expected_profit(self, input, confidence: float) -> Decimal:
        # use Decimal arithmetic
        price_a = Decimal(str(input.price_a))
        price_b = Decimal(str(input.price_b))
        borrow_amount = Decimal(str(input.borrow_amount_usdc))
        gross_spread = (abs(price_a - price_b) / min(price_a, price_b))
        expected_gross = borrow_amount * gross_spread
        cost_adjustment = borrow_amount * Decimal("0.0057")
        expected_profit = (expected_gross - cost_adjustment) * Decimal(str(confidence))
        return expected_profit

    def rank_opportunities(self, inputs: List) -> List[Tuple[object, float]]:
        scored = []
        for inp in inputs:
            conf, risk = self.score_single(inp)
            exp_prof = self.calculate_expected_profit(inp, conf)
            # value-weighted score
            score = float(conf) * float(exp_prof)
            scored.append((inp, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:MAX_CONCURRENT_POSITIONS]
