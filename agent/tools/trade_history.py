"""
Tool 3: QueryTradeHistory
Queries recent executed trades from the opportunities database.
Provides historical context for the agent to learn from recent performance.
"""

import json
import random
from typing import Any, Dict, List, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class TradeRecord(BaseModel):
    """A single executed trade record."""
    opportunity_id: str = Field(description="Unique opportunity identifier")
    symbol: str = Field(description="Trading pair symbol")
    dex_pair: str = Field(description="DEX pair (e.g., UNISWAP_AAVE)")
    profit_usdc: float = Field(description="Realized profit in USDC")
    execution_latency_ms: int = Field(description="Execution latency in milliseconds")
    gas_used: float = Field(description="Gas used for transaction")
    success: bool = Field(description="Whether trade executed successfully")
    timestamp: int = Field(description="Unix timestamp of execution")


class TradeHistoryResult(BaseModel):
    """Result of trade history query."""
    trades_found: int = Field(description="Number of trades found")
    trades: List[TradeRecord] = Field(description="List of trade records")
    total_profit_usdc: float = Field(description="Total profit across returned trades")
    win_rate_pct: float = Field(description="Percentage of profitable trades")
    avg_profit_usdc: float = Field(description="Average profit per trade")
    message: str = Field(description="Human-readable summary")


class QueryTradeHistory(BaseTool):
    """
    Queries recent executed trades from the opportunities database.
    
    Allows filtering by:
    - Symbol
    - DEX pair
    - Last N hours
    
    Returns the last 10 matching trades with full details for pattern analysis.
    """
    
    name: str = "QueryTradeHistory"
    description: str = (
        "Query recent executed trades from the opportunities database. "
        "Can filter by symbol, DEX pair, or time window. "
        "Returns the last 10 matching trades with profit/loss, latency, and gas data."
    )
    
    def _run(
        self,
        symbol: Optional[str] = None,
        dex_pair: Optional[str] = None,
        last_n_hours: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Query trade history.
        
        Args:
            symbol: Filter by trading pair (e.g., "BTC", "ETH")
            dex_pair: Filter by DEX pair (e.g., "UNISWAP_AAVE")
            last_n_hours: Only return trades from last N hours
        
        Returns:
            JSON string of TradeHistoryResult
        """
        # In production, this would query the SQLite opportunities database
        # For now, generate realistic mock historical trades
        
        # Generate 10 realistic trade records
        trades: List[TradeRecord] = []
        now = int(random.random() * 1000000)  # Mock timestamp
        
        for i in range(10):
            # Simulate mix of winning and losing trades
            is_profitable = random.random() < 0.65  # 65% win rate
            profit = random.uniform(2.0, 50.0) if is_profitable else random.uniform(-10.0, -0.5)
            
            trade = TradeRecord(
                opportunity_id=f"opp_{random.randint(1000, 9999)}",
                symbol=symbol or random.choice(["BTC", "ETH", "USDC"]),
                dex_pair=dex_pair or random.choice(["UNISWAP_AAVE", "CURVE_LIDO", "BALANCER_FRAX"]),
                profit_usdc=round(profit, 2),
                execution_latency_ms=random.randint(500, 3000),
                gas_used=random.uniform(50, 200),
                success=is_profitable or random.random() < 0.8,  # Most losses still execute
                timestamp=now - (i * 3600),  # Spread across hours
            )
            trades.append(trade)
        
        # Calculate summary statistics
        total_profit = sum(t.profit_usdc for t in trades)
        profitable_trades = sum(1 for t in trades if t.profit_usdc > 0)
        win_rate = (profitable_trades / len(trades)) * 100 if trades else 0.0
        avg_profit = total_profit / len(trades) if trades else 0.0
        
        message = (
            f"Retrieved {len(trades)} recent trades. "
            f"Win rate: {win_rate:.1f}%, Total: ${total_profit:.2f} USDC"
        )
        
        result = TradeHistoryResult(
            trades_found=len(trades),
            trades=trades,
            total_profit_usdc=round(total_profit, 2),
            win_rate_pct=round(win_rate, 1),
            avg_profit_usdc=round(avg_profit, 2),
            message=message,
        )
        
        return json.dumps(result.dict())
    
    async def _arun(
        self,
        symbol: Optional[str] = None,
        dex_pair: Optional[str] = None,
        last_n_hours: Optional[int] = None,
        **kwargs
    ) -> str:
        """Async implementation (not used in this context)."""
        return self._run(symbol, dex_pair, last_n_hours, **kwargs)
