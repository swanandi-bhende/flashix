from decimal import Decimal
import json
from hashlib import sha256
from dataclasses import replace

MIN_PROFIT_USDC = Decimal("10")


class SignalBuilder:
    def _build_reasoning_string(self, input, confidence, risk_score, expected_profit, decision):
        price_a = float(input.price_a)
        price_b = float(input.price_b)
        gross_spread = float(abs(price_a - price_b) / min(price_a, price_b) * 100.0)
        return f"Spread={gross_spread:.2f}%, Confidence={confidence:.2f}, Risk={risk_score:.2f}, ExpectedProfit=${expected_profit:.4f}, Decision={decision}"

    def build(self, input, confidence: float, risk_score: float, expected_profit: Decimal, model_metadata) -> object:
        borrow_amount = Decimal(str(input.borrow_amount_usdc))
        collateral_required = borrow_amount * Decimal("1.5")
        expiry_timestamp = int(input.timestamp) + 30
        gross_spread = float(abs(float(input.price_a) - float(input.price_b)) / min(float(input.price_a), float(input.price_b)) * 100.0)
        liquidity_floor = min(float(input.orderbook_depth_a), float(input.orderbook_depth_b))
        funding_diff = abs(float(input.funding_rate_a - input.funding_rate_b))
        suspicious_market = (
            gross_spread > 10.0
            or liquidity_floor < 1000.0
            or float(input.volatility_24h) >= 4.0
            or funding_diff >= 0.008
            or float(input.gas_price_gwei) >= 100.0
        )
        decision = "EXECUTE" if (not suspicious_market and confidence > 0.75 and risk_score < 0.6 and expected_profit > MIN_PROFIT_USDC) else "SKIP"
        reasoning = self._build_reasoning_string(input, confidence, risk_score, expected_profit, decision)

        input_dict = input.__dict__
        input_hash = sha256(json.dumps(input_dict, sort_keys=True, default=str).encode()).hexdigest()

        out_small = {
            "decision": decision,
            "expected_profit": str(expected_profit),
            "risk_score": float(risk_score),
            "expiry_timestamp": int(expiry_timestamp),
        }
        output_hash = sha256(json.dumps(out_small, sort_keys=True, default=str).encode()).hexdigest()

        from compute.arbitrage_analyzer import InferenceOutput

        out = InferenceOutput(
            opportunity_id=input.opportunity_id,
            primary_dex=input.dex_a,
            counter_dex=input.dex_b,
            borrow_amount=borrow_amount,
            collateral_required=collateral_required,
            expected_profit_usdc=expected_profit,
            risk_score=float(risk_score),
            confidence=float(confidence),
            decision=decision,
            expiry_timestamp=expiry_timestamp,
            reasoning=reasoning,
            model_version=model_metadata.version if hasattr(model_metadata, "version") else str(model_metadata),
            input_hash=input_hash,
            output_hash=output_hash,
            tee_signature="",
        )
        return out
