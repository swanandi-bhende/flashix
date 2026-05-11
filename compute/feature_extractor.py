from dataclasses import dataclass
import numpy as np
from decimal import Decimal

class FeatureExtractionError(Exception):
    pass


@dataclass
class FeatureExtractor:
    def extract(self, input) -> np.ndarray:
        # strict deterministic transforms
        try:
            price_a = float(input.price_a)
            price_b = float(input.price_b)
            gross_spread_percent = float(abs(price_a - price_b) / min(price_a, price_b) * 100.0)

            funding_rate_diff = float(input.funding_rate_a - input.funding_rate_b)
            borrow_amount_log = float(np.log1p(float(input.borrow_amount_usdc)))
            orderbook_depth_ratio = float(input.orderbook_depth_a / (input.orderbook_depth_b + 1e-9))
            trade_flow_imbalance_diff = float(input.trade_flow_imbalance_a - input.trade_flow_imbalance_b)
            volatility_24h = float(np.clip(input.volatility_24h, 0.0, 5.0))
            correlation_btc = float(np.clip(input.correlation_btc, -1.0, 1.0))
            time_of_day_sin = float(np.sin(2 * np.pi * (input.timestamp % 86400) / 86400))
            time_of_day_cos = float(np.cos(2 * np.pi * (input.timestamp % 86400) / 86400))
            day_of_week = float((input.timestamp // 86400) % 7)
            gas_price_gwei = float(np.clip(input.gas_price_gwei, 1.0, 500.0))
            spread_momentum_5s = float(input.spread_momentum_5s)

            vec = np.array([
                gross_spread_percent,
                funding_rate_diff,
                borrow_amount_log,
                orderbook_depth_ratio,
                trade_flow_imbalance_diff,
                volatility_24h,
                correlation_btc,
                time_of_day_sin,
                time_of_day_cos,
                day_of_week,
                gas_price_gwei,
                spread_momentum_5s,
            ], dtype=np.float64)

            self.validate_feature_vector(vec)
            return vec

        except Exception as e:
            raise FeatureExtractionError(str(e))

    def validate_feature_vector(self, vec: np.ndarray):
        if vec.shape != (12,):
            raise FeatureExtractionError(f"Invalid feature vector shape: {vec.shape}")
        if np.isnan(vec).any():
            raise FeatureExtractionError("NaN present in feature vector")
        if np.isinf(vec).any():
            raise FeatureExtractionError("Inf present in feature vector")
