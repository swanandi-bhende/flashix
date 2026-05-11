# Market Data Pipeline Architecture

## Overview

The Flashix market data service provides **live oracle aggregation, freshness monitoring, and REST API access** to trusted consensus pricing across multiple decentralized and centralized sources.

The system implements a **three-tier fallback cascade** (Pyth → Chainlink → 1inch) with **median-based aggregation** for manipulation resistance, and **circuit breaker integration** to pause execution when oracle quality degrades below safe thresholds.

## Oracle Source Comparison

| Metric | Pyth Network | Chainlink | 1inch |
|--------|--------------|-----------|-------|
| **Update Frequency** | Real-time (WebSocket) | 1–5 min (heartbeat/deviation) | On-demand API calls |
| **Decentralization** | 80+ price providers | 1000+ node operators | DEX aggregator (centralized) |
| **Manipulation Resistance** | High (distributed aggregation) | Very High (established) | Medium (liquidity-dependent) |
| **Latency** | 50–100ms (p95) | 100–200ms (RPC call) | 150–300ms (API + slippage) |
| **Cost** | Free (Hermes WebSocket) | Gas for on-chain reads | API rate-limited (free tier: 1 RPS) |
| **Data Format** | Price + confidence intervals | AggregatorV3Interface | Swap quotes + estimated gas |
| **Best For** | Primary pricing, speed | Fallback, on-chain validation | Slippage estimation |

## Fallback Cascade

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent Needs Price                               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Try Pyth (ACTIVE)?     │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┴────────────────────────┐
        │                                                  │
        ▼ YES (VALID)                                    ▼ NO/STALE
    ┌────────────────┐                         ┌────────────────────┐
    │ RETURN PYTH    │                         │ Try Chainlink?     │
    │ SAMPLE         │                         └────────────────────┘
    └────────────────┘                                    │
                                         ┌─────────────────┴─────────────────┐
                                         │                                   │
                                         ▼ YES                             ▼ NO
                                    ┌──────────────┐          ┌─────────────────────┐
                                    │RETURN CHAIN- │          │ Try 1inch/DEX?      │
                                    │LINK SAMPLE   │          └─────────────────────┘
                                    └──────────────┘                   │
                                                         ┌─────────────┴──────────────┐
                                                         │                            │
                                                         ▼ YES                      ▼ NO
                                                    ┌──────────────┐     ┌────────────────────┐
                                                    │RETURN 1INCH  │     │ OPEN CIRCUIT       │
                                                    │SAMPLE        │     │ BREAKER: ORACLE    │
                                                    └──────────────┘     │ FAILURE            │
                                                                         │ HALT EXECUTION     │
                                                                         └────────────────────┘
```

## Aggregation Algorithm

The `OracleAggregator` merges raw samples using **median-based consensus** for outlier resistance:

### Step 1: Filter Valid Samples
- Retain only samples where `is_valid=True` and `staleness_ms <= 500`
- Track which sources succeeded vs. failed

### Step 2: Compute Initial Consensus
- Extract `mid_price` from each valid sample
- Compute `consensus_price = median(prices)`
- Median is more robust than mean for manipulation detection

### Step 3: Detect & Exclude Manipulation
- For each sample, compute deviation: `abs(price - consensus) / consensus * 100`
- If `deviation > 0.5%` (MANIPULATION_DETECTION_THRESHOLD_PCT):
  - Log `ORACLE_DEVIATION_ALERT` at WARNING level
  - **Remove from consensus calculation** (don't just flag)
- Recompute consensus without outliers

### Step 4: Classify Data Quality
```
num_sources = 3  →  HIGH      (best)
num_sources = 2  →  MEDIUM    (safe to execute)
num_sources = 1  →  LOW       (single point of failure, risky)
num_sources = 0  →  UNAVAILABLE (pause execution)
```

### Step 5: Compute Funding Rate & Collateral Consensus
- Median funding_rate across valid sources
- Median collateral_ratio across valid sources

## Freshness Monitoring

### Target Freshness
- **MAX_STALENESS_MS = 500** — any sample older than 500ms is flagged
- **Pyth:** target <100ms (WebSocket streaming)
- **Chainlink:** target <150ms (on-chain poll with 2s interval)
- **1inch:** target <300ms (API call + routing)

### Violation Detection
The `FreshnessMonitor` records every staleness violation to SQLite for **post-trade P&L attribution**:
- When `sample.staleness_ms > MAX_STALENESS_MS`, insert into `freshness_violations` table
- Join violations with trade records to identify if an execution was impacted by stale data
- Example: *"Trade ABC-123 executed with stale Pyth data (650ms), Chainlink was fresh (80ms) — should have used Chainlink"*

### Data Gap Detection
- Expected inter-sample interval ≈ 500ms
- Gap detected when consecutive samples are >3x expected interval apart
- Logged as `DataGap(symbol, gap_start_ms, gap_end_ms, duration_ms, missing_samples_estimate)`

### Benchmarking
Per-oracle latency statistics (p50, p95, p99, max) from last 1000 fetches:
```python
benchmark = freshness_monitor.benchmark_source_latency()
# {OracleSource.PYTH: LatencyBenchmark(p50=45ms, p95=95ms, p99=120ms, max=200ms, ...)}
```

## In-Memory Sliding Window Store

The `MarketStateWindowStore` maintains a **1000-sample, 10-minute rolling window** per symbol:

```python
window = MarketStateWindow(
    symbol="BTC-USD-PERP",
    samples=deque(maxlen=1000),  # Auto-evicts oldest when full
    window_start_ms=...,
    window_end_ms=...,
    sample_count=...
)
```

### Statistical Queries

#### Volatility
```python
volatility = window_store.get_volatility("BTC-USD-PERP", window_seconds=60)
# Returns annualized volatility using log returns
# volatility = std(log_returns) * sqrt(samples_per_second * window_seconds)
```

#### Correlation
```python
correlation = window_store.get_price_correlation("BTC-USD-PERP", "ETH-USD-PERP", window_seconds=300)
# Returns Pearson correlation coefficient in [-1, 1]
# Aligns samples by timestamp (nearest neighbor within 200ms)
```

#### Spread Momentum
```python
momentum = window_store.get_spread_momentum("BTC-USD-PERP", dex_a="Uniswap", dex_b="0x", window_seconds=5)
# Returns rate of change of bid-ask spread over last 5 seconds
# Used by inference feature extractor as spread_momentum_5s
```

## Circuit Breaker Integration

When **all three oracle sources fail**, the system opens the `BreakerType.ORACLE_FAILURE` circuit breaker:

```python
# In FallbackOrchestrator._trigger_execution_pause()
risk_registry.open_breaker(
    breaker_type=BreakerType.ORACLE_FAILURE,
    trigger_value=0.0,
    opportunity_id=None,
    auto_reset_seconds=None,  # Manual reset required
    notes=f"Oracle failure for {symbol}: {reason}"
)
```

This immediately halts all execution across the board. Recovery is automatic when oracles restore:

```python
# Background monitor every 10 seconds
if oracle_recovered():
    risk_registry.close_breaker(
        breaker_type=BreakerType.ORACLE_FAILURE,
        resolution_method="ORACLE_RECOVERED"
    )
    # Execution resumes
```

## REST API Endpoints (Port 8003)

### Market Data (Hot Path)

#### `GET /market/{symbol}/latest`
**Most frequently called endpoint** — agent queries before every trade.

```json
{
  "symbol": "BTC-USD-PERP",
  "consensus_price": "45000.50",
  "price_std_dev": "10.25",
  "max_deviation_pct": 0.15,
  "funding_rate": "0.0001",
  "collateral_ratio": "2.5",
  "data_quality": "HIGH",
  "sources_used": ["PYTH", "CHAINLINK", "ONE_INCH"],
  "sources_failed": [],
  "aggregated_at_ms": 1234567890000,
  "oldest_source_staleness_ms": 45
}
```

#### `GET /market/{symbol}/window?window_seconds=300`
Returns rolling history for correlation analysis.

```json
[
  {
    "timestamp_ms": 1234567880000,
    "consensus_price": "45000.00",
    "data_quality": "HIGH",
    "sources_used": ["PYTH", "CHAINLINK", "ONE_INCH"]
  },
  ...
]
```

#### `GET /market/{symbol}/volatility?window_seconds=60`
Annualized volatility for the symbol.

```json
{
  "symbol": "BTC-USD-PERP",
  "volatility": 0.65,
  "window_seconds": 60,
  "sample_count": 120,
  "computed_at_ms": 1234567890000
}
```

#### `GET /market/{symbol_a}/correlation/{symbol_b}?window_seconds=300`
Pearson correlation between two symbols.

```json
{
  "symbol_a": "BTC-USD-PERP",
  "symbol_b": "ETH-USD-PERP",
  "correlation": 0.78,
  "window_seconds": 300,
  "sample_count": 600,
  "computed_at_ms": 1234567890000
}
```

### Monitoring & Analytics

#### `GET /market/health`
**For Demo**: Show judges live oracle status and execution safety.

```json
{
  "sources": {
    "PYTH": "ACTIVE",
    "CHAINLINK": "ACTIVE",
    "ONE_INCH": "DEGRADED"
  },
  "freshness": {
    "BTC-USD-PERP": 45,
    "ETH-USD-PERP": 50
  },
  "data_quality": {
    "BTC-USD-PERP": "HIGH",
    "ETH-USD-PERP": "MEDIUM"
  },
  "execution_safe": true,
  "staleness_violations_last_hour": 3,
  "computed_at_ms": 1234567890000
}
```

#### `GET /market/freshness/report`
Detailed freshness metrics per symbol.

```json
[
  {
    "symbol": "BTC-USD-PERP",
    "total_samples": 1200,
    "violation_count": 2,
    "violation_rate_pct": 0.17,
    "avg_staleness_ms": 48,
    "p95_staleness_ms": 120,
    "recommendation": "Pyth is consistently fresher than Chainlink by 180ms p95 — increase Pyth weight in aggregation"
  }
]
```

#### `GET /market/oracle/deviation`
**For Demo**: Show if any manipulation was detected during the trading session.

```json
[
  {
    "symbol": "BTC-USD-PERP",
    "deviating_source": "ONE_INCH",
    "deviation_pct": 0.75,
    "detected_at_ms": 1234567850000
  }
]
```

## Freshness Setup

### 1. Initialize Monitors

```python
from agent.market_data import (
    PythOracleClient,
    ChainlinkOracleClient,
    OneInchClient,
    OracleAggregator,
    MarketStateWindowStore,
    FallbackOrchestrator,
    FreshnessMonitor,
)

# Start clients
pyth_client = PythOracleClient()
asyncio.create_task(pyth_client.start())

chainlink_client = ChainlinkOracleClient(rpc_endpoint="https://0g-rpc.example.com")
chainlink_client.start_monitoring()

oneinch_client = OneInchClient(chain_id=1)

# Create aggregator and window store
aggregator = OracleAggregator()
window_store = MarketStateWindowStore(tracked_symbols=["BTC-USD-PERP", "ETH-USD-PERP"])

# Create orchestrator for fallback cascade
fallback_orchestrator = FallbackOrchestrator(
    pyth_client=pyth_client,
    chainlink_client=chainlink_client,
    oneinch_client=oneinch_client,
    risk_registry=risk_manager.registry,
    aggregator=aggregator,
)
fallback_orchestrator.start_recovery_monitor()

# Create freshness monitor
freshness_monitor = FreshnessMonitor(data_dir="data")
```

### 2. Main Loop: Ingest and Aggregate

```python
async def market_data_loop():
    while True:
        # Fetch latest samples from all sources
        raw_samples = []
        
        # Pyth (already streaming via WebSocket)
        pyth_sample = pyth_client.get_latest("BTC-USD-PERP")
        if pyth_sample:
            raw_samples.append(pyth_sample)
        
        # Chainlink (polled every 2s)
        chainlink_sample = chainlink_client.get_latest("BTC-USD-PERP")
        if chainlink_sample:
            raw_samples.append(chainlink_sample)
        
        # 1inch (on-demand)
        # Called only if needed for slippage estimation
        
        # Aggregate
        aggregated = aggregator.aggregate("BTC-USD-PERP", raw_samples)
        window_store.record(aggregated)
        
        # Record freshness metrics
        for sample in raw_samples:
            freshness_monitor.record_sample_received(sample)
        
        # Check if safe to execute
        safe, reason = aggregator.is_safe_to_execute(aggregated)
        
        await asyncio.sleep(0.5)  # Aggregate ~2x per second
```

### 3. Query API for Agent

```python
# Before executing a trade, agent calls:
response = requests.get("http://localhost:8003/market/BTC-USD-PERP/latest")
market_state = response.json()

if market_state["data_quality"] == "HIGH" or market_state["data_quality"] == "MEDIUM":
    # Execute trade with this consensus price
    consensus_price = Decimal(market_state["consensus_price"])
    ...
else:
    # Pause execution
    ...
```

## Demo Walkthrough (For Judges)

### 1. Show Live Oracle Status
```bash
curl http://localhost:8003/market/health
```
Shows:
- Which oracles are ACTIVE/DEGRADED/FAILED
- Freshness metrics (staleness in ms)
- Data quality per symbol
- Whether execution is safe

### 2. Show Deviation Alerts
```bash
curl http://localhost:8003/market/oracle/deviation
```
If any oracle was flagged for potential manipulation, it appears here.

### 3. Show Freshness Report
```bash
curl http://localhost:8003/market/freshness/report
```
Detailed staleness statistics and auto-generated recommendations.

### 4. Query Specific Price
```bash
curl http://localhost:8003/market/BTC-USD-PERP/latest
```
Shows the consensus price the agent is using.

### 5. Inspect Trade Data With Staleness
```sql
SELECT t.trade_id, t.executed_price, m.staleness_ms, m.source
FROM trades t
JOIN market_data_at_execution m ON t.id = m.trade_id
WHERE m.staleness_ms > 500;
```
Post-trade analysis: identify which trades executed with stale data.

## Key Invariants

1. **Consensus uses median, not mean** → Outlier resistance
2. **Outliers are excluded, not flagged** → Prevents contamination
3. **Fallback is automatic, not operator-driven** → No human latency
4. **Circuit breaker is non-blocking** → Trading resumes on recovery
5. **All violations are logged** → Full auditability
6. **Freshness is benchmarked** → Data-driven optimization

## Deployment Checklist

- [ ] Update `PYTH_PRICE_IDS` in `/agent/market_data.py` with real Pyth feed IDs
- [ ] Update `CHAINLINK_FEED_ADDRESSES` with real contract addresses for your chain
- [ ] Update `ONE_INCH_TOKENS` with real token addresses and decimals
- [ ] Set `ONE_INCH_API_KEY` environment variable (optional, increases rate limits)
- [ ] Configure `CHAINLINK_RPC_ENDPOINT` (separate from trading RPC to avoid rate-limiting)
- [ ] Start REST API on port 8003 with `uvicorn agent.market_data.api:app --port 8003`
- [ ] Verify oracle recovery monitor is running
- [ ] Test fallback cascade with manual source disabling
- [ ] Verify circuit breaker integration with risk system
- [ ] Validate freshness metrics against SLA targets

## References

- **Pyth Network**: https://docs.pyth.network/
- **Chainlink**: https://docs.chain.link/
- **1inch**: https://docs.1inch.io/
- **Consensus Algorithms**: https://en.wikipedia.org/wiki/Median_(statistics)
