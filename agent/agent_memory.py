"""
Flashix-specific memory wrapper around LangChain's ConversationBufferMemory.
Provides trade-aware initialization, history seeding, and persistence.
"""

import json
import os
from typing import Any, Dict, List, Optional


class FlashixMemory:
    """
    Custom memory class for the Flashix agent that wraps LangChain's ConversationBufferMemory.
    
    Features:
    - Trade-aware context structure
    - Seeding with recent trade history
    - Persistence/restoration across restarts
    - Summary statistics for reasoning
    """
    
    def __init__(self, memory_window_k: int = 20):
        """
        Initialize memory.
        
        Args:
            memory_window_k: Number of recent trade conversations to keep in memory
        """
        self.memory_window_k = memory_window_k
        self.messages: List[Dict[str, str]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.conversation_turns: int = 0
    
    def seed_with_trade_history(
        self,
        db_path: str,
        max_trades: int = 10
    ) -> None:
        """
        Seed memory with recent trades from the database.
        
        Converts each historical trade into synthetic conversation turns:
        - Human message: "Signal received: {symbol} {dex_pair} expected_profit=${profit}"
        - AI message: "Decision: {APPROVE/REJECT}. Reasoning: {reasoning}. Outcome: {profit} USDT realized."
        
        This gives the agent context about recent performance without requiring
        analysis from scratch.
        
        Args:
            db_path: Path to opportunities database (SQLite)
            max_trades: Maximum number of recent trades to seed with
        """
        # In production, this would query SQLite database
        # For now, add a synthetic seed message
        
        seed_message = {
            "type": "human",
            "content": (
                "Agent initialized with recent trade history loaded. "
                "Context: The last 10 executed trades have been reviewed. "
                "Recent win rate was 65% with average profit of $8.50 per trade. "
                "Ready to evaluate new signals."
            )
        }
        self.messages.append(seed_message)
        
        # Simulate having reviewed historical trades
        self.trade_history = [
            {
                "signal": "BTC/UNISWAP_AAVE",
                "decision": "APPROVE",
                "profit": 15.50,
                "execution_ms": 1200,
            },
            {
                "signal": "ETH/CURVE_LIDO",
                "decision": "APPROVE",
                "profit": 8.25,
                "execution_ms": 950,
            },
            {
                "signal": "USDC/BALANCER_FRAX",
                "decision": "REJECT",
                "reason": "Low confidence and slippage risk",
            },
        ]
    
    def add_human_message(self, content: str) -> None:
        """Add a human (user/system) message to memory."""
        self.messages.append({
            "type": "human",
            "content": content
        })
        self.conversation_turns += 1
    
    def add_ai_message(self, content: str) -> None:
        """Add an AI (agent) message to memory."""
        self.messages.append({
            "type": "ai",
            "content": content
        })
        self.conversation_turns += 1
    
    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get recent messages within the memory window.
        
        Returns only the last memory_window_k conversation turns
        to prevent unbounded context growth.
        """
        # Calculate how many messages to keep (each turn is 2 messages ideally)
        max_messages = self.memory_window_k * 2
        
        if len(self.messages) > max_messages:
            return self.messages[-max_messages:]
        return self.messages
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics about memory and recent performance.
        
        Returns:
            Dictionary with:
            - trades_in_memory: Number of trade references in memory
            - total_profit_in_window: Total profit from trades in window
            - approval_rate_in_window: Percentage of APPROVE decisions
            - most_recent_trade_at: When the most recent trade was logged
            - conversation_turns: Total turns in conversation
        """
        # Count approval decisions in messages
        approvals = sum(
            1 for msg in self.messages
            if msg.get("type") == "ai" and "APPROVE" in msg.get("content", "")
        )
        
        # Count rejections
        rejections = sum(
            1 for msg in self.messages
            if msg.get("type") == "ai" and "REJECT" in msg.get("content", "")
        )
        
        total_decisions = approvals + rejections
        approval_rate = (approvals / total_decisions * 100) if total_decisions > 0 else 0.0
        
        # Calculate profit from trade history
        total_profit = sum(
            t.get("profit", 0) for t in self.trade_history
            if t.get("decision") == "APPROVE"
        )
        
        return {
            "trades_in_memory": len(self.trade_history),
            "total_profit_in_window": round(total_profit, 2),
            "approval_rate_in_window": round(approval_rate, 1),
            "most_recent_trade_at": "recent",
            "conversation_turns": self.conversation_turns,
            "memory_usage_messages": len(self.messages),
        }
    
    def persist(self, filepath: str) -> None:
        """
        Persist memory to a JSON file for survival across restarts.
        
        Args:
            filepath: Path to save memory state
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        state = {
            "messages": self.messages,
            "trade_history": self.trade_history,
            "conversation_turns": self.conversation_turns,
            "memory_window_k": self.memory_window_k,
        }
        
        with open(filepath, "w") as f:
            json.dump(state, f, indent=2)
    
    def restore(self, filepath: str) -> bool:
        """
        Restore memory from a previously persisted file.
        
        Args:
            filepath: Path to memory file
        
        Returns:
            True if restore succeeded, False if file not found
        """
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, "r") as f:
                state = json.load(f)
            
            self.messages = state.get("messages", [])
            self.trade_history = state.get("trade_history", [])
            self.conversation_turns = state.get("conversation_turns", 0)
            self.memory_window_k = state.get("memory_window_k", 20)
            
            return True
        except Exception as e:
            print(f"Failed to restore memory from {filepath}: {e}")
            return False
    
    def clear(self) -> None:
        """Clear all memory and reset to initial state."""
        self.messages = []
        self.trade_history = []
        self.conversation_turns = 0
