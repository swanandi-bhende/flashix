"""
Tool 2: AssessMarketConditions
Assesses current market conditions including gas prices, funding rates, liquidity, and volatility.
"""

import json
import random
from typing import Any, Dict

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class MarketAssessment(BaseModel):
    """Result of market condition assessment."""
    gas_price_gwei: float = Field(description="Current gas price in Gwei")
    gas_spike_detected: bool = Field(description="Whether gas has spiked >30%")
    funding_rate_favorable: bool = Field(description="Whether funding rate is favorable")
    liquidity_adequate: bool = Field(description="Whether orderbook has adequate depth")
    volatility_level: str = Field(description="Market volatility: LOW, MEDIUM, or HIGH")
    recommendation: str = Field(description="Recommendation: PROCEED, WAIT, or ABORT")
    baseline_gas_price_gwei: float = Field(description="Baseline gas price for comparison")
    current_funding_rate_pct: float = Field(description="Current funding rate percentage")
    orderbook_depth_usd: float = Field(description="Total orderbook depth in USD")
    volatility_pct_5m: float = Field(description="5-minute price volatility percentage")


class AssessMarketConditions(BaseTool):
    """
    Assesses current market conditions for execution.
    
    Evaluates:
    - Gas price and whether it's spiking
    - Funding rate favorability
    - Orderbook liquidity
    - 5-minute price volatility
    
    Returns structured MarketAssessment with recommendation.
    """
    
    name: str = "AssessMarketConditions"
    description: str = (
        "Assess current market conditions for the given trading pair. "
        "Fetches gas price, funding rates, orderbook depth, and volatility. "
        "Returns detailed metrics and a recommendation (PROCEED/WAIT/ABORT)."
    )
    
    def _run(
        self,
        symbol: str = "BTC",
        dex_pair: str = "UNISWAP_AAVE",
        gas_spike_threshold_pct: float = 30.0,
        **kwargs
    ) -> str:
        """
        Assess market conditions.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC", "ETH")
            dex_pair: DEX pair string (e.g., "UNISWAP_AAVE")
            gas_spike_threshold_pct: Threshold for detecting gas spikes
        
        Returns:
            JSON string of MarketAssessment
        """
        # In production, this would fetch actual data from:
        # - ethers.provider.getFeeData()
        # - DEX price feed APIs
        # - Orderbook snapshots
        # - Price feeds for volatility calculation
        
        # For now, return realistic mock data
        baseline_gas = 50.0  # Gwei (typical baseline)
        current_gas = baseline_gas * random.uniform(0.8, 1.5)  # Simulate variance
        gas_change_pct = ((current_gas - baseline_gas) / baseline_gas) * 100
        gas_spike_detected = gas_change_pct > gas_spike_threshold_pct
        
        # Funding rates (favorable = positive for our position)
        funding_rate = random.uniform(-0.01, 0.02)  # -1% to +2%
        funding_favorable = funding_rate > 0.002  # > 0.2% is favorable
        
        # Liquidity simulation
        orderbook_depth = random.uniform(500000, 5000000)  # $500k to $5M
        liquidity_adequate = orderbook_depth > 100000  # Need at least $100k
        
        # Volatility simulation (5-minute)
        volatility = random.uniform(0.5, 5.0)  # 0.5% to 5%
        if volatility < 1.5:
            volatility_level = "LOW"
        elif volatility < 3.0:
            volatility_level = "MEDIUM"
        else:
            volatility_level = "HIGH"
        
        # Recommendation logic
        if gas_spike_detected:
            recommendation = "ABORT"  # Never proceed with gas spike
        elif not liquidity_adequate:
            recommendation = "ABORT"  # Never proceed without liquidity
        elif volatility_level == "HIGH" and not funding_favorable:
            recommendation = "WAIT"  # High volatility without favorable funding
        else:
            recommendation = "PROCEED"
        
        assessment = MarketAssessment(
            gas_price_gwei=round(current_gas, 2),
            gas_spike_detected=gas_spike_detected,
            funding_rate_favorable=funding_favorable,
            liquidity_adequate=liquidity_adequate,
            volatility_level=volatility_level,
            recommendation=recommendation,
            baseline_gas_price_gwei=baseline_gas,
            current_funding_rate_pct=round(funding_rate * 100, 3),
            orderbook_depth_usd=round(orderbook_depth, 2),
            volatility_pct_5m=round(volatility, 2),
        )
        
        return json.dumps(assessment.dict())
    
    async def _arun(self, symbol: str, dex_pair: str, **kwargs) -> str:
        """Async implementation (not used in this context)."""
        return self._run(symbol, dex_pair, **kwargs)
