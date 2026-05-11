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

        liquidity_floor = min(float(input.orderbook_depth_a), float(input.orderbook_depth_b))
        funding_diff = abs(float(input.funding_rate_a - input.funding_rate_b))
        volatility = float(input.volatility_24h)
        gas_price = float(input.gas_price_gwei)

        if liquidity_floor < 1000.0:
            confidence *= 0.4
        if volatility >= 4.0:
            confidence *= 0.6
        if funding_diff >= 0.008:
            confidence *= 0.5
        if gas_price >= 150.0:
            confidence *= 0.75

        confidence = max(0.0, min(1.0, confidence))
        risk_score = max(
            0.0,
            min(
                1.0,
                1.0 - confidence
                + (0.25 if liquidity_floor < 1000.0 else 0.0)
                + (0.20 if volatility >= 4.0 else 0.0)
                + (0.20 if funding_diff >= 0.008 else 0.0)
                + (0.10 if gas_price >= 150.0 else 0.0),
            ),
        )
        return confidence, risk_score

    def calculate_expected_profit(self, input, confidence: float) -> Decimal:
        # use Decimal arithmetic
        price_a = Decimal(str(input.price_a))
        price_b = Decimal(str(input.price_b))
        borrow_amount = Decimal(str(input.borrow_amount_usdc))
        funding_diff = abs(Decimal(str(input.funding_rate_a)) - Decimal(str(input.funding_rate_b)))
        liquidity_floor = Decimal(str(min(float(input.orderbook_depth_a), float(input.orderbook_depth_b))))
        gas_price = Decimal(str(float(input.gas_price_gwei)))
        gross_spread = (abs(price_a - price_b) / min(price_a, price_b))
        expected_gross = borrow_amount * gross_spread
        cost_adjustment = borrow_amount * Decimal("0.0057")
        funding_penalty = borrow_amount * funding_diff * Decimal("10")
        liquidity_penalty = max(Decimal("0"), Decimal("1000") - liquidity_floor) * Decimal("0.10")
        gas_penalty = gas_price * Decimal("0.05")
        expected_profit = (expected_gross - cost_adjustment - funding_penalty - liquidity_penalty - gas_penalty) * Decimal(str(confidence))
        return max(Decimal("0"), expected_profit)

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
