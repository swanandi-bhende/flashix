from decimal import Decimal
from agent.agent_config import AgentConfig

TESTNET_AGENT_CONFIG = AgentConfig(
    gemini_model="gemini-1.5-flash",
    gemini_temperature=0.3,
    max_iterations=5,
    max_execution_time_seconds=20,
    memory_window_k=15,
    min_confidence_threshold=0.78,
    min_profit_usdc=Decimal("1.50"),
    max_concurrent_positions=2,
    gas_price_spike_threshold_pct=25.0,
    require_explicit_approval=False,
    dry_run_mode=False,
    chain_id=16600,
)

# Testnet-specific risk parameters
MIN_COLLATERAL_RATIO = Decimal("1.6")
DAILY_LOSS_CAP_USDC = Decimal("-20.0")
MAX_SLIPPAGE_PCT = 1.5
POSITION_TIMEOUT_SECONDS = 25
