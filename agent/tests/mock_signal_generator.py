"""
Mock signal generator for testing agent reasoning consistency.
Generates 50+ diverse test scenarios covering all decision paths.
"""

import random
import time
from typing import List

from signal_processor import InferenceOutput


class MockSignalGenerator:
    """
    Generates synthetic InferenceOutput signals covering diverse scenarios.
    Used for testing the agent before live trading.
    """
    
    def __init__(self, seed: int = 42):
        """
        Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        random.seed(seed)
        self.now = int(time.time())
    
    def generate_clear_approve_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        High confidence (0.90+), large spread (5%+), low risk, ample expiry time.
        Agent should APPROVE all of these.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"clear_approve_{i}",
                symbol=random.choice(["BTC", "ETH", "USDC"]),
                primary_dex=random.choice(["UNISWAP", "CURVE", "BALANCER"]),
                counter_dex=random.choice(["AAVE", "LIDO", "FRAX"]),
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.05, 1.15),  # 5-15% spread
                gross_spread_percent=random.uniform(5.0, 15.0),
                borrow_amount=random.uniform(50000, 500000),
                collateral_required=random.uniform(10000, 100000),
                expected_profit_usdc=random.uniform(10.0, 100.0),  # Good profit
                confidence=random.uniform(0.90, 0.99),  # High confidence
                risk_score=random.uniform(0.1, 0.3),  # Low risk
                expiry_timestamp=self.now + 28,  # 28 seconds to expiry
                decision="EXECUTE",
                tee_signature="sig_" + "a" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_low_profit_reject_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        High confidence (0.80+) but net profit < $2.
        Agent should REJECT all of these.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"low_profit_{i}",
                symbol=random.choice(["BTC", "ETH", "USDC"]),
                primary_dex=random.choice(["UNISWAP", "CURVE"]),
                counter_dex=random.choice(["AAVE", "LIDO"]),
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.02, 1.04),  # Small spread
                gross_spread_percent=random.uniform(2.0, 4.0),
                borrow_amount=random.uniform(50000, 500000),
                collateral_required=random.uniform(10000, 100000),
                expected_profit_usdc=random.uniform(0.5, 1.99),  # Below $2 threshold
                confidence=random.uniform(0.80, 0.95),
                risk_score=random.uniform(0.2, 0.4),
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "b" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_low_confidence_reject_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Profitable spread but confidence < 0.75.
        Agent should REJECT all of these.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"low_conf_{i}",
                symbol=random.choice(["BTC", "ETH"]),
                primary_dex=random.choice(["UNISWAP", "CURVE"]),
                counter_dex=random.choice(["AAVE", "LIDO"]),
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.04, 1.10),
                gross_spread_percent=random.uniform(4.0, 10.0),
                borrow_amount=random.uniform(100000, 1000000),
                collateral_required=random.uniform(20000, 200000),
                expected_profit_usdc=random.uniform(5.0, 50.0),  # Profitable
                confidence=random.uniform(0.50, 0.74),  # Below threshold
                risk_score=random.uniform(0.5, 0.9),
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "c" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_borderline_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Exactly at thresholds: confidence 0.76, profit $2.05.
        Agent should handle consistently.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"borderline_{i}",
                symbol="BTC",
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=50000.0,
                price_b=51000.0,
                gross_spread_percent=2.0,
                borrow_amount=250000.0,
                collateral_required=50000.0,
                expected_profit_usdc=2.05,  # Just above $2 threshold
                confidence=0.76,  # Just above 0.75 threshold
                risk_score=0.45,
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "d" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_expiring_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Valid signal but only 8 seconds to expiry.
        Agent should consider time urgency.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"expiring_{i}",
                symbol=random.choice(["BTC", "ETH"]),
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.05, 1.12),
                gross_spread_percent=random.uniform(5.0, 12.0),
                borrow_amount=random.uniform(100000, 500000),
                collateral_required=random.uniform(20000, 100000),
                expected_profit_usdc=random.uniform(10.0, 50.0),
                confidence=random.uniform(0.80, 0.95),
                risk_score=random.uniform(0.2, 0.4),
                expiry_timestamp=self.now + 8,  # Only 8 seconds!
                decision="EXECUTE",
                tee_signature="sig_" + "e" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_high_gas_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Valid signal but simulated high gas environment.
        Agent should check gas conditions (via AssessMarketConditions).
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"high_gas_{i}",
                symbol=random.choice(["BTC", "ETH"]),
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.06, 1.14),
                gross_spread_percent=random.uniform(6.0, 14.0),
                borrow_amount=random.uniform(100000, 500000),
                collateral_required=random.uniform(20000, 100000),
                expected_profit_usdc=random.uniform(15.0, 60.0),
                confidence=random.uniform(0.82, 0.96),
                risk_score=random.uniform(0.2, 0.4),
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "f" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_low_liquidity_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Valid signal but low liquidity environment.
        Agent should check via AssessMarketConditions.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"low_liquidity_{i}",
                symbol=random.choice(["BTC", "ETH"]),
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=random.uniform(100, 10000),
                price_b=random.uniform(100, 10000) * random.uniform(1.05, 1.13),
                gross_spread_percent=random.uniform(5.0, 13.0),
                borrow_amount=random.uniform(50000, 200000),
                collateral_required=random.uniform(10000, 50000),
                expected_profit_usdc=random.uniform(8.0, 40.0),
                confidence=random.uniform(0.78, 0.92),
                risk_score=random.uniform(0.3, 0.6),
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "1" * 64,
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_invalid_signature_signals(self, count: int = 5) -> List[InferenceOutput]:
        """
        Tampered TEE signature.
        ValidateInferenceSignal should reject these immediately.
        """
        signals = []
        for i in range(count):
            signal = InferenceOutput(
                opportunity_id=f"invalid_sig_{i}",
                symbol="BTC",
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=50000.0,
                price_b=52500.0,
                gross_spread_percent=5.0,
                borrow_amount=250000.0,
                collateral_required=50000.0,
                expected_profit_usdc=25.0,
                confidence=0.90,
                risk_score=0.2,
                expiry_timestamp=self.now + 25,
                decision="EXECUTE",
                tee_signature="invalid",  # Too short, will fail validation
                model_version="arbitrage_scorer_v1",
            )
            signals.append(signal)
        return signals
    
    def generate_all_test_signals(self) -> List[InferenceOutput]:
        """
        Generate all 50+ test signals covering all scenarios.
        
        Returns:
            List of InferenceOutput signals for testing
        """
        all_signals = []
        all_signals.extend(self.generate_clear_approve_signals(5))
        all_signals.extend(self.generate_low_profit_reject_signals(5))
        all_signals.extend(self.generate_low_confidence_reject_signals(5))
        all_signals.extend(self.generate_borderline_signals(5))
        all_signals.extend(self.generate_expiring_signals(5))
        all_signals.extend(self.generate_high_gas_signals(5))
        all_signals.extend(self.generate_low_liquidity_signals(5))
        all_signals.extend(self.generate_invalid_signature_signals(5))
        
        return all_signals
