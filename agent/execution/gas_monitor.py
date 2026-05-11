"""
Gas price monitor and dynamic fee strategy.
Provides real-time gas intelligence to prevent execution during gas spikes.
"""

import time
import logging
import threading
from typing import Optional, List, Literal
from decimal import Decimal

from web3 import Web3

from agent.execution_engine import (
    GasFees,
    ViabilityCheck,
    GasSpikeDetected,
    MAX_GAS_UNITS,
)

_logger = logging.getLogger(__name__)

# Default ETH price for cost estimation (will be updated from chain)
DEFAULT_ETH_PRICE_USDC = Decimal("2500")

# Historical base fee for spike detection (7-day average)
HISTORICAL_BASE_FEE_GWEI = Decimal("30")

# Gas spike detection threshold (130% of 7-day average)
GAS_SPIKE_THRESHOLD_MULTIPLIER = Decimal("1.3")


class GasMonitor:
    """
    Real-time gas price monitor with dynamic fee strategy.
    
    Provides gas intelligence to ensure that gas costs never silently erode
    arbitrage margins below profitability.
    """
    
    def __init__(self, web3: Optional[Web3] = None, poll_interval_seconds: int = 5):
        """
        Initialize the gas monitor.
        
        Args:
            web3: Web3 instance connected to 0G Chain
            poll_interval_seconds: How often to poll gas prices (background thread)
        """
        self.web3 = web3
        self.poll_interval_seconds = poll_interval_seconds
        self.current_fees: Optional[GasFees] = None
        self.last_spike_detected: bool = False
        self.last_update_time = 0
        self.lock = threading.Lock()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Start background polling
        if self.web3:
            self.start_monitoring()
    
    def start_monitoring(self) -> None:
        """Start the background gas price monitoring thread."""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._background_poll,
            daemon=True
        )
        self.monitor_thread.start()
        _logger.debug("Gas monitor background thread started")
    
    def stop_monitoring(self) -> None:
        """Stop the background gas price monitoring thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        _logger.debug("Gas monitor background thread stopped")
    
    def _background_poll(self) -> None:
        """Background thread that polls gas prices every poll_interval_seconds."""
        while self.running:
            try:
                self.get_current_fees()
            except Exception as e:
                _logger.warning(f"Background gas poll failed: {e}")
            
            time.sleep(self.poll_interval_seconds)
    
    def get_current_fees(self) -> GasFees:
        """
        Get current gas fee structure from fee_history.
        
        Calls web3.eth.fee_history(10, 'latest', [25, 50, 75]) to get the last
        10 blocks' base fees and priority fee percentiles.
        
        Returns:
            GasFees with current gas prices and spike detection
        """
        
        try:
            # Get fee history for last 10 blocks
            fee_history = self.web3.eth.fee_history(10, 'latest', [25, 50, 75])
            
            # Extract base fees
            base_fees_wei = fee_history.get('baseFeePerGas', [])
            if not base_fees_wei:
                base_fee_gwei = float(self.web3.to_wei(1, 'gwei')) / 1e9
            else:
                # Use the base fee from the latest block
                base_fee_gwei = float(base_fees_wei[-1]) / 1e9
            
            # Extract priority fees (25th, 50th, 75th percentiles)
            priority_fees = fee_history.get('reward', [[0, 0, 0]] * 10)
            
            # Average the priority fees across the 10 blocks
            priority_fees_25 = []
            priority_fees_50 = []
            priority_fees_75 = []
            
            for block_fees in priority_fees:
                if len(block_fees) >= 3:
                    priority_fees_25.append(float(block_fees[0]) / 1e9)
                    priority_fees_50.append(float(block_fees[1]) / 1e9)
                    priority_fees_75.append(float(block_fees[2]) / 1e9)
            
            priority_fee_p25_gwei = (
                sum(priority_fees_25) / len(priority_fees_25)
                if priority_fees_25 else 1.0
            )
            priority_fee_p50_gwei = (
                sum(priority_fees_50) / len(priority_fees_50)
                if priority_fees_50 else 1.0
            )
            priority_fee_p75_gwei = (
                sum(priority_fees_75) / len(priority_fees_75)
                if priority_fees_75 else 2.0
            )
            
            # Recommended maxFeePerGas = base_fee * 1.5 + priority_fee_p50
            max_fee_gwei = base_fee_gwei * 1.5 + priority_fee_p50_gwei
            
            # ================================================================
            # GAS SPIKE DETECTION
            # ================================================================
            # Check if current base fee is 30% above 7-day average
            spike_detected = base_fee_gwei > float(HISTORICAL_BASE_FEE_GWEI * GAS_SPIKE_THRESHOLD_MULTIPLIER)
            
            if spike_detected:
                spike_severity: Literal["NONE", "MODERATE", "SEVERE"] = "SEVERE"
            elif base_fee_gwei > float(HISTORICAL_BASE_FEE_GWEI * Decimal("1.1")):
                spike_severity = "MODERATE"
            else:
                spike_severity = "NONE"
            
            # Get ETH price for cost estimation (use fixed default for now)
            eth_price_usdc = DEFAULT_ETH_PRICE_USDC
            
            # Estimate gas cost in USDC
            estimated_cost_usdc = float(
                (Decimal(str(max_fee_gwei)) / Decimal("1e9"))
                * Decimal(str(MAX_GAS_UNITS))
                * eth_price_usdc
            )
            
            fees = GasFees(
                base_fee_gwei=base_fee_gwei,
                priority_fee_p25_gwei=priority_fee_p25_gwei,
                priority_fee_p50_gwei=priority_fee_p50_gwei,
                max_fee_gwei=max_fee_gwei,
                estimated_cost_usdc=estimated_cost_usdc,
                spike_detected=spike_detected,
                spike_severity=spike_severity,
            )
            
            with self.lock:
                if spike_detected and not self.last_spike_detected:
                    _logger.critical(
                        f"GAS_SPIKE_ALERT: base_fee_gwei={base_fee_gwei:.2f}, "
                        f"historical_average={float(HISTORICAL_BASE_FEE_GWEI):.2f}"
                    )
                self.last_spike_detected = spike_detected
                self.current_fees = fees
                self.last_update_time = int(time.time())
            
            _logger.debug(
                f"GAS_FEES_UPDATED: base_fee={base_fee_gwei:.2f}gwei, "
                f"max_fee={max_fee_gwei:.2f}gwei, "
                f"spike_detected={spike_detected}, "
                f"estimated_cost=${estimated_cost_usdc:.2f}"
            )
            
            return fees
        
        except Exception as e:
            _logger.error(f"Error fetching gas fees: {e}")
            # Return default fees if fetch fails
            return GasFees(
                base_fee_gwei=float(HISTORICAL_BASE_FEE_GWEI),
                priority_fee_p25_gwei=1.0,
                priority_fee_p50_gwei=1.5,
                max_fee_gwei=float(HISTORICAL_BASE_FEE_GWEI) * 1.5 + 1.5,
                estimated_cost_usdc=float(
                    Decimal(str(HISTORICAL_BASE_FEE_GWEI)) / Decimal("1e9")
                    * Decimal(str(MAX_GAS_UNITS))
                    * DEFAULT_ETH_PRICE_USDC
                ),
                spike_detected=False,
                spike_severity="NONE",
            )
    
    def is_execution_viable(
        self, expected_profit_usdc: Decimal, max_gas_price_gwei: Optional[float] = None
    ) -> ViabilityCheck:
        """
        Check if execution is viable given current gas conditions.
        
        Marks not viable if:
        1. spike_severity == "SEVERE" (gas spike detected)
        2. estimated_cost_usdc > expected_profit_usdc * 0.3 (gas consuming > 30% of profit)
        3. max_fee_gwei > max_gas_price_gwei from request (exceeds hard cap)
        
        Args:
            expected_profit_usdc: Expected profit from the arbitrage signal
        
        Returns:
            ViabilityCheck with viable=True/False and reasoning
        """
        
        # Get current fees (from cache if available)
        with self.lock:
            fees = self.current_fees
        
        if fees is None:
            # Try one synchronous fetch
            try:
                fees = self.get_current_fees()
            except Exception as e:
                return ViabilityCheck(
                    viable=False,
                    reason=f"Failed to fetch gas fees: {e}",
                    gas_cost_usdc=0.0,
                    profit_after_gas=Decimal("0"),
                    margin_pct=0.0,
                )
        
        # ================================================================
        # CHECK 1: Gas spike detection
        # ================================================================
        if fees.spike_severity == "SEVERE":
            _logger.critical(
                f"GAS_EXECUTION_BLOCKED: reason=SEVERE_GAS_SPIKE, "
                f"base_fee={fees.base_fee_gwei}gwei"
            )
            raise GasSpikeDetected(
                f"Severe gas spike detected: base_fee={fees.base_fee_gwei:.2f}gwei"
            )

        if max_gas_price_gwei is not None and fees.max_fee_gwei > max_gas_price_gwei:
            reason = (
                f"Recommended max fee {fees.max_fee_gwei:.2f} gwei exceeds request cap "
                f"{max_gas_price_gwei:.2f} gwei"
            )
            _logger.critical(f"GAS_EXECUTION_BLOCKED: {reason}")
            return ViabilityCheck(
                viable=False,
                reason=reason,
                gas_cost_usdc=fees.estimated_cost_usdc,
                profit_after_gas=expected_profit_usdc - Decimal(str(fees.estimated_cost_usdc)),
                margin_pct=float(
                    ((expected_profit_usdc - Decimal(str(fees.estimated_cost_usdc))) / expected_profit_usdc) * Decimal("100")
                    if expected_profit_usdc > 0 else Decimal("0")
                ),
            )
        
        # ================================================================
        # CHECK 2: Gas cost relative to profit
        # ================================================================
        gas_cost_usdc = fees.estimated_cost_usdc
        max_allowed_gas_cost = float(expected_profit_usdc * Decimal("0.3"))
        
        if gas_cost_usdc > max_allowed_gas_cost:
            reason = (
                f"Gas cost ${gas_cost_usdc:.2f} exceeds 30% of profit "
                f"${expected_profit_usdc:.2f}"
            )
            _logger.critical(f"GAS_EXECUTION_BLOCKED: {reason}")
            
            profit_after_gas = expected_profit_usdc - Decimal(str(gas_cost_usdc))
            margin_pct = float(
                (profit_after_gas / expected_profit_usdc * Decimal("100"))
                if expected_profit_usdc > 0 else Decimal("0")
            )
            
            return ViabilityCheck(
                viable=False,
                reason=reason,
                gas_cost_usdc=gas_cost_usdc,
                profit_after_gas=profit_after_gas,
                margin_pct=margin_pct,
            )
        
        # ================================================================
        # ALL CHECKS PASSED
        # ================================================================
        profit_after_gas = expected_profit_usdc - Decimal(str(gas_cost_usdc))
        margin_pct = float(
            (profit_after_gas / expected_profit_usdc * Decimal("100"))
            if expected_profit_usdc > 0 else Decimal("0")
        )
        
        _logger.debug(
            f"GAS_VIABILITY_PASSED: gas_cost=${gas_cost_usdc:.2f}, "
            f"profit_after_gas=${profit_after_gas:.2f}, "
            f"margin_pct={margin_pct:.2f}%"
        )
        
        return ViabilityCheck(
            viable=True,
            reason="Gas conditions acceptable",
            gas_cost_usdc=gas_cost_usdc,
            profit_after_gas=profit_after_gas,
            margin_pct=margin_pct,
        )
