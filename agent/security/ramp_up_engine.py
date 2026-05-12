"""
Gradual Ramp-Up Engine — Graduated capital exposure strategy with automated advancement.

This module enforces the graduated capital exposure strategy, ensuring the system proves 
itself at each capital tier before advancing to the next. The ramp-up starts at $50 per 
trade and doubles every 6 hours with zero losses, enabling safe scaling from minimal to 
full capital deployment.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import requests


# Configure logging
logger = logging.getLogger(__name__)


class RampUpError(Exception):
    """Raised when ramp-up engine encounters an error."""
    pass


class RampUpStateError(Exception):
    """Raised when ramp-up state is corrupted or invalid."""
    pass


@dataclass
class RampUpTier:
    """Definition of a capital tier in the ramp-up schedule."""
    tier: int
    borrow_amount_usdc: Decimal
    min_hours: int  # Minimum hours at this tier before advancement
    min_trades: int  # Minimum trades at this tier before advancement


@dataclass
class RampUpState:
    """Persistent ramp-up state (stored to JSON for crash recovery)."""
    current_tier: int
    tier_start_time: datetime
    trades_at_tier: int
    cumulative_profit_at_tier: Decimal
    zero_losses_at_tier: bool
    total_trades_completed: int
    total_profit_usdc: Decimal
    last_updated: datetime = field(default_factory=datetime.utcnow)


class RampUpEngine:
    """
    Manages graduated capital exposure strategy.
    
    The ramp-up schedule allows the system to prove itself at increasingly higher 
    capital levels. Advancement requires:
    1. Minimum time at tier (6-24 hours depending on tier)
    2. Minimum trade count at tier (3-20 trades)
    3. Zero losses during the tier period
    
    If a loss occurs, advancement is paused until manual team review and reset.
    """
    
    # Ramp-up schedule: 6 tiers from $50 to $1600
    RAMP_UP_SCHEDULE: List[RampUpTier] = [
        RampUpTier(tier=1, borrow_amount_usdc=Decimal("50"), min_hours=6, min_trades=3),
        RampUpTier(tier=2, borrow_amount_usdc=Decimal("100"), min_hours=6, min_trades=5),
        RampUpTier(tier=3, borrow_amount_usdc=Decimal("200"), min_hours=6, min_trades=8),
        RampUpTier(tier=4, borrow_amount_usdc=Decimal("400"), min_hours=6, min_trades=10),
        RampUpTier(tier=5, borrow_amount_usdc=Decimal("800"), min_hours=12, min_trades=15),
        RampUpTier(tier=6, borrow_amount_usdc=Decimal("1600"), min_hours=24, min_trades=20),
    ]
    
    def __init__(self, 
                 data_dir: str = "data",
                 ops_webhook_url: Optional[str] = None):
        """
        Initialize the ramp-up engine.
        
        Args:
            data_dir: Directory for storing ramp-up state.
            ops_webhook_url: URL for sending ops notifications (optional).
            
        Raises:
            RampUpStateError: If state file is corrupted.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "ramp_up_state.json"
        self.ops_webhook_url = ops_webhook_url or os.getenv("OPS_WEBHOOK_URL", "")
        
        # Load or initialize state
        self.state = self._load_state()
        
        logger.info(
            f"Ramp-up engine initialized: tier={self.state.current_tier}, "
            f"borrow_amount=${self.get_current_borrow_amount()}, "
            f"trades_at_tier={self.state.trades_at_tier}"
        )
    
    def _load_state(self) -> RampUpState:
        """
        Load ramp-up state from JSON file, or initialize if not exists.
        
        Returns:
            RampUpState: The current ramp-up state.
            
        Raises:
            RampUpStateError: If state file is corrupted.
        """
        if not self.state_file.exists():
            # Initialize to tier 1
            state = RampUpState(
                current_tier=1,
                tier_start_time=datetime.utcnow(),
                trades_at_tier=0,
                cumulative_profit_at_tier=Decimal("0"),
                zero_losses_at_tier=True,
                total_trades_completed=0,
                total_profit_usdc=Decimal("0"),
            )
            self._save_state(state)
            return state
        
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            
            state = RampUpState(
                current_tier=data["current_tier"],
                tier_start_time=datetime.fromisoformat(data["tier_start_time"]),
                trades_at_tier=data["trades_at_tier"],
                cumulative_profit_at_tier=Decimal(str(data["cumulative_profit_at_tier"])),
                zero_losses_at_tier=data["zero_losses_at_tier"],
                total_trades_completed=data["total_trades_completed"],
                total_profit_usdc=Decimal(str(data["total_profit_usdc"])),
                last_updated=datetime.fromisoformat(data["last_updated"]),
            )
            return state
        except Exception as e:
            raise RampUpStateError(f"Failed to load ramp-up state: {e}")
    
    def _save_state(self, state: RampUpState) -> None:
        """
        Save ramp-up state to JSON file.
        
        Args:
            state: The ramp-up state to save.
        """
        try:
            data = {
                "current_tier": state.current_tier,
                "tier_start_time": state.tier_start_time.isoformat(),
                "trades_at_tier": state.trades_at_tier,
                "cumulative_profit_at_tier": str(state.cumulative_profit_at_tier),
                "zero_losses_at_tier": state.zero_losses_at_tier,
                "total_trades_completed": state.total_trades_completed,
                "total_profit_usdc": str(state.total_profit_usdc),
                "last_updated": datetime.utcnow().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ramp-up state: {e}")
    
    def _send_ops_webhook(self, event: str, data: dict) -> None:
        """
        Send a notification webhook to the ops team.
        
        Args:
            event: Event name (e.g., "RAMP_UP_ADVANCE", "RAMP_UP_LOSS_DETECTED").
            data: Event data to include in webhook.
        """
        if not self.ops_webhook_url:
            logger.debug(f"Ops webhook not configured; skipping notification for {event}")
            return
        
        try:
            payload = {
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            }
            response = requests.post(self.ops_webhook_url, json=payload, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Ops webhook returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to send ops webhook: {e}")
    
    def get_current_borrow_amount(self) -> Decimal:
        """
        Get the current tier's borrow amount.
        
        Process:
        1. Read current_tier from persistent state
        2. Check whether advancement criteria are met
        3. If criteria met, advance to next tier
        4. Return current tier's borrow amount
        
        Returns:
            Decimal: The current tier's borrow amount in USDC.
        """
        current_tier_config = self.RAMP_UP_SCHEDULE[self.state.current_tier - 1]
        
        # Check if advancement criteria are met
        if self._check_advancement_criteria():
            # Advance to next tier
            if self.state.current_tier < len(self.RAMP_UP_SCHEDULE):
                old_tier = self.state.current_tier
                self.state.current_tier += 1
                self.state.tier_start_time = datetime.utcnow()
                self.state.trades_at_tier = 0
                self.state.cumulative_profit_at_tier = Decimal("0")
                self.state.zero_losses_at_tier = True
                self._save_state(self.state)
                
                new_tier_config = self.RAMP_UP_SCHEDULE[self.state.current_tier - 1]
                logger.info(
                    f"RAMP_UP_ADVANCE: tier={old_tier}→{self.state.current_tier}, "
                    f"borrow_amount=${current_tier_config.borrow_amount_usdc}→"
                    f"${new_tier_config.borrow_amount_usdc}"
                )
                
                # Send ops webhook
                self._send_ops_webhook(
                    "RAMP_UP_ADVANCE",
                    {
                        "old_tier": old_tier,
                        "new_tier": self.state.current_tier,
                        "new_borrow_amount_usdc": str(new_tier_config.borrow_amount_usdc),
                    },
                )
                
                current_tier_config = new_tier_config
        
        return current_tier_config.borrow_amount_usdc
    
    def _check_advancement_criteria(self) -> bool:
        """
        Check if current tier advancement criteria are met.
        
        Criteria:
        1. hours_at_tier >= tier.min_hours
        2. trades_at_tier >= tier.min_trades
        3. zero_losses_at_tier == True
        4. current_tier < max tier
        
        Returns:
            bool: True if all criteria are met.
        """
        if self.state.current_tier >= len(self.RAMP_UP_SCHEDULE):
            # Already at max tier
            return False
        
        current_tier_config = self.RAMP_UP_SCHEDULE[self.state.current_tier - 1]
        
        # Check time requirement
        hours_at_tier = (datetime.utcnow() - self.state.tier_start_time).total_seconds() / 3600
        if hours_at_tier < current_tier_config.min_hours:
            return False
        
        # Check trade requirement
        if self.state.trades_at_tier < current_tier_config.min_trades:
            return False
        
        # Check loss requirement
        if not self.state.zero_losses_at_tier:
            return False
        
        return True
    
    def report_trade_outcome(self, profit_usdc: Decimal) -> None:
        """
        Report the outcome of a completed trade.
        
        Updates tier statistics and halts advancement if a loss is detected.
        
        Args:
            profit_usdc: Profit (positive) or loss (negative) from the trade.
        """
        # Update state
        self.state.trades_at_tier += 1
        self.state.cumulative_profit_at_tier += profit_usdc
        self.state.total_trades_completed += 1
        self.state.total_profit_usdc += profit_usdc
        
        # Check for losses
        if profit_usdc < Decimal("0"):
            self.state.zero_losses_at_tier = False
            self._save_state(self.state)
            
            logger.warning(
                f"RAMP_UP_LOSS_DETECTED: amount=${abs(profit_usdc):.4f}, "
                f"tier={self.state.current_tier}, advancement_paused"
            )
            
            # Send ops webhook
            self._send_ops_webhook(
                "RAMP_UP_LOSS_DETECTED",
                {
                    "loss_amount_usdc": str(abs(profit_usdc)),
                    "tier": self.state.current_tier,
                    "trades_at_tier": self.state.trades_at_tier,
                    "cumulative_profit_at_tier": str(self.state.cumulative_profit_at_tier),
                },
            )
        else:
            self._save_state(self.state)
    
    def force_rollback(self, n_tiers: int = 1) -> None:
        """
        Manually rollback to a lower tier.
        
        For use when the ops team detects degrading market conditions and wants 
        to reduce exposure.
        
        Args:
            n_tiers: Number of tiers to rollback (default 1).
        """
        new_tier = max(1, self.state.current_tier - n_tiers)
        if new_tier == self.state.current_tier:
            logger.info(f"Rollback requested but already at tier {self.state.current_tier}")
            return
        
        old_tier = self.state.current_tier
        self.state.current_tier = new_tier
        self.state.tier_start_time = datetime.utcnow()
        self.state.trades_at_tier = 0
        self.state.cumulative_profit_at_tier = Decimal("0")
        self.state.zero_losses_at_tier = True
        self._save_state(self.state)
        
        new_tier_config = self.RAMP_UP_SCHEDULE[self.state.current_tier - 1]
        logger.warning(
            f"RAMP_UP_ROLLBACK: tier={old_tier}→{new_tier}, "
            f"borrow_amount=${new_tier_config.borrow_amount_usdc}"
        )
        
        # Send ops webhook
        self._send_ops_webhook(
            "RAMP_UP_ROLLBACK",
            {
                "old_tier": old_tier,
                "new_tier": new_tier,
                "reason": "manual_rollback",
            },
        )
    
    def reset_zero_losses_flag(self) -> None:
        """
        Reset the zero-losses flag to allow advancement after a loss.
        
        This is called after the ops team has reviewed a loss and determined 
        it was acceptable (e.g., due to market conditions beyond the system's control).
        
        This requires the RAMP_UP_RESET_TOKEN from the ops team to prevent 
        accidental resets.
        """
        if not self.state.zero_losses_at_tier:
            self.state.zero_losses_at_tier = True
            self._save_state(self.state)
            
            logger.info(
                f"RAMP_UP_LOSS_RESET: tier={self.state.current_tier} "
                f"advancement re-enabled after loss review"
            )
            
            # Send ops webhook
            self._send_ops_webhook(
                "RAMP_UP_LOSS_RESET",
                {
                    "tier": self.state.current_tier,
                },
            )
        else:
            logger.info("Reset requested but no losses detected")
    
    def get_status(self) -> dict:
        """
        Get detailed status of the ramp-up engine.
        
        Returns:
            dict: Status information including current tier, progress, and statistics.
        """
        current_tier_config = self.RAMP_UP_SCHEDULE[self.state.current_tier - 1]
        hours_at_tier = (datetime.utcnow() - self.state.tier_start_time).total_seconds() / 3600
        
        return {
            "current_tier": self.state.current_tier,
            "borrow_amount_usdc": str(current_tier_config.borrow_amount_usdc),
            "tier_start_time": self.state.tier_start_time.isoformat(),
            "hours_at_tier": round(hours_at_tier, 2),
            "min_hours_required": current_tier_config.min_hours,
            "trades_at_tier": self.state.trades_at_tier,
            "min_trades_required": current_tier_config.min_trades,
            "cumulative_profit_at_tier": str(self.state.cumulative_profit_at_tier),
            "zero_losses_at_tier": self.state.zero_losses_at_tier,
            "total_trades_completed": self.state.total_trades_completed,
            "total_profit_usdc": str(self.state.total_profit_usdc),
            "can_advance": self._check_advancement_criteria(),
            "max_tier": len(self.RAMP_UP_SCHEDULE),
        }
