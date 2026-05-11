"""
Centralized agent configuration dataclass with environment variable loading.
All parameters are validated at startup to prevent silent misconfiguration failures.
"""

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


class ConfigurationError(Exception):
    """Raised when a configuration parameter is invalid or missing."""
    def __init__(self, field_name: str, value: any, reason: str):
        self.field_name = field_name
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid {field_name}={value}: {reason}")


@dataclass
class AgentConfig:
    """Complete agent configuration loaded from environment."""
    
    # LLM Configuration
    gemini_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.3
    gemini_max_tokens: int = 2048
    
    # Agent Execution Parameters
    max_iterations: int = 5  # Maximum reasoning steps before forcing decision
    max_execution_time_seconds: float = 25.0  # 5 second buffer before 30s signal expiry
    
    # Memory Configuration
    memory_window_k: int = 20  # Last 20 trade conversations
    
    # Decision Thresholds
    min_confidence_threshold: float = 0.75
    min_profit_usdc: Decimal = field(default_factory=lambda: Decimal("2.0"))
    max_concurrent_positions: int = 3
    
    # Market Condition Thresholds
    gas_price_spike_threshold_pct: float = 30.0  # Gas price must not spike >30% above baseline
    
    # Safety Constraints
    require_explicit_approval: bool = True  # Never execute without explicit approval log
    dry_run_mode: bool = True  # Only set to False in production
    
    # Blockchain Configuration
    chain_id: int = 16600  # 0G Chain
    tee_address: str = ""
    signal_validator_address: str = ""
    arbitrage_executor_address: str = ""
    
    # Logging
    verbose: bool = True  # Print intermediate steps during development
    
    def validate(self):
        """Validate all parameters are within acceptable ranges."""
        if not (0.0 <= self.gemini_temperature <= 1.0):
            raise ConfigurationError(
                "gemini_temperature",
                self.gemini_temperature,
                "must be between 0.0 and 1.0 (lower = more deterministic)"
            )
        
        if self.gemini_max_tokens < 512:
            raise ConfigurationError(
                "gemini_max_tokens",
                self.gemini_max_tokens,
                "must be >= 512 for adequate reasoning output"
            )
        
        if self.max_iterations < 1:
            raise ConfigurationError(
                "max_iterations",
                self.max_iterations,
                "must be >= 1"
            )
        
        if self.max_execution_time_seconds < 1.0 or self.max_execution_time_seconds > 25.0:
            raise ConfigurationError(
                "max_execution_time_seconds",
                self.max_execution_time_seconds,
                "must be between 1.0 and 25.0 seconds"
            )
        
        if not (0.0 <= self.min_confidence_threshold <= 1.0):
            raise ConfigurationError(
                "min_confidence_threshold",
                self.min_confidence_threshold,
                "must be between 0.0 and 1.0"
            )
        
        if self.min_profit_usdc < Decimal("0"):
            raise ConfigurationError(
                "min_profit_usdc",
                float(self.min_profit_usdc),
                "must be non-negative"
            )
        
        if self.gas_price_spike_threshold_pct <= 0:
            raise ConfigurationError(
                "gas_price_spike_threshold_pct",
                self.gas_price_spike_threshold_pct,
                "must be positive"
            )
        
        if self.memory_window_k < 1:
            raise ConfigurationError(
                "memory_window_k",
                self.memory_window_k,
                "must be >= 1"
            )
        
        if not self.tee_address:
            raise ConfigurationError(
                "tee_address",
                self.tee_address,
                "cannot be empty; set TEE_ADDRESS environment variable"
            )
        
        if not self.signal_validator_address:
            raise ConfigurationError(
                "signal_validator_address",
                self.signal_validator_address,
                "cannot be empty; set SIGNAL_VALIDATOR_ADDRESS environment variable"
            )
        
        if not self.arbitrage_executor_address:
            raise ConfigurationError(
                "arbitrage_executor_address",
                self.arbitrage_executor_address,
                "cannot be empty; set ARBITRAGE_EXECUTOR_ADDRESS environment variable"
            )
    
    @classmethod
    def load_from_env(cls) -> "AgentConfig":
        """
        Load configuration from environment variables with type casting and validation.
        
        Raises ConfigurationError if any parameter is invalid.
        """
        try:
            config = cls(
                gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
                gemini_max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "2048")),
                max_iterations=int(os.getenv("MAX_ITERATIONS", "5")),
                max_execution_time_seconds=float(os.getenv("MAX_EXECUTION_TIME_SECONDS", "25.0")),
                memory_window_k=int(os.getenv("MEMORY_WINDOW_K", "20")),
                min_confidence_threshold=float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.75")),
                min_profit_usdc=Decimal(os.getenv("MIN_PROFIT_USDC", "2.0")),
                max_concurrent_positions=int(os.getenv("MAX_CONCURRENT_POSITIONS", "3")),
                gas_price_spike_threshold_pct=float(os.getenv("GAS_PRICE_SPIKE_THRESHOLD_PCT", "30.0")),
                require_explicit_approval=os.getenv("REQUIRE_EXPLICIT_APPROVAL", "true").lower() == "true",
                dry_run_mode=os.getenv("DRY_RUN_MODE", "true").lower() == "true",
                chain_id=int(os.getenv("CHAIN_ID", "16600")),
                tee_address=os.getenv("TEE_ADDRESS", ""),
                signal_validator_address=os.getenv("SIGNAL_VALIDATOR_ADDRESS", ""),
                arbitrage_executor_address=os.getenv("ARBITRAGE_EXECUTOR_ADDRESS", ""),
                verbose=os.getenv("VERBOSE", "true").lower() == "true",
            )
            config.validate()
            return config
        except ValueError as e:
            raise ConfigurationError(
                "type_conversion",
                str(e),
                f"Failed to convert environment variable to expected type: {e}"
            )
