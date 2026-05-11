# Mempool Ingestion Pipeline Architecture

## Overview

The Flashix mempool ingestion pipeline is a high-performance, event-driven system that processes private mempool data, detects arbitrage opportunities, filters them for profitability, and forwards high-quality signals to the 0G Compute TEE inference layer.

The pipeline operates in two modes:
- **Live Mode**: Connects to real private mempool providers (Bloxroute, Eden Network, MEV-Relay)
- **Simulation Mode**: Generates synthetic market data for development and testing (zero external dependencies)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MEMPOOL DATA SOURCES                                │
│                                                                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Bloxroute Elite  │  │  Eden Network    │  │   MEV-Relay      │          │
│  │ (Primary)        │  │  (Fallback 1)    │  │  (Fallback 2)    │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│           └─────────────────────┼─────────────────────┘                     │
│                                 │                                           │
│                    WebSocket: newTxs, dexSnapshots                          │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
         ┌──────────────────────┐   ┌──────────────────────┐
         │  INGESTER.JS         │   │  SIMULATOR.JS        │
         │  (Live Provider      │   │  (Dev/Testing Mode)  │
         │   Connection)        │   │                      │
         │                      │   │  • High Volatility   │
         │  • WebSocket mgmt    │   │  • Low Volatility    │
         │  • Auth header       │   │  • Congestion        │
         │  • Reconnect logic   │   │  • Rapid Reversion   │
         │  • Event routing     │   │                      │
         └──────────┬───────────┘   └──────────┬───────────┘
                    │                          │
                    └──────────────┬───────────┘
                                   │
                  HTTP Status Endpoint: /status, /health, /metrics
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │   INGESTER EMITTER                   │
                    │  (EventEmitter)                      │
                    │                                      │
                    │  • mempool-txs event                 │
                    │  • dex-snapshot event                │
                    │  • bdn-block event                   │
                    └──────────────┬───────────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
                ▼                  ▼                  ▼
      ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
      │DEX_PRICE_FEED.JS│   │[MEMPOOL TXNS]   │   │[BDN BLOCKS]     │
      │                 │   │(Link with       │   │(Context Data)   │
      │Polls 500ms:     │   │ opportunities)  │   │                 │
      │• Aave Perps     │   │                 │   │                 │
      │• Hyperliquid    │   └─────────────────┘   └─────────────────┘
      │• dYdX           │
      │                 │
      │Mark/Index Price │
      │Funding Rates    │
      │Collateral Rate  │
      │                 │
      │In-Memory Map:   │
      │{symbol:dex} →   │
      │{price, rate,    │
      │ staleness}      │
      └────────┬────────┘
               │
               │ getPriceSpread(symbol, dex_a, dex_b)
               │ → {spread%, funding_rate_diff}
               │
               ▼
      ┌─────────────────────────────────────┐
      │OPPORTUNITY_DETECTOR.JS              │
      │                                     │
      │Scan @ 100ms intervals (matches      │
      │mempool cadence):                    │
      │                                     │
      │For each market {BTC, ETH, ARB}      │
      │ For each DEX pair (Aave-HL,         │
      │                    Aave-dYdX,       │
      │                    HL-dYdX):        │
      │   if |spread| > 0.5%:               │
      │     emit OpportunityCandidate       │
      │     (id, symbol, dex_a, dex_b,     │
      │      price_a, price_b, spread%,    │
      │      funding_diff, tx_hash)        │
      │                                     │
      │Status: DETECTED                     │
      └────────┬────────────────────────────┘
               │
               │ Candidate Events (100ms+)
               │
               ▼
      ┌──────────────────────────────────────┐
      │COST_CALCULATOR.JS                    │
      │                                      │
      │For each candidate, compute:          │
      │                                      │
      │1. Flashloan Fee: amount * 0.09%      │
      │2. Funding Rate: |diff| * period      │
      │3. Slippage (tiered):                 │
      │   <$10k: 0.2%                        │
      │   $10-50k: 0.35%                     │
      │   >$50k: 0.5%                        │
      │4. Gas Cost: gas_units * price        │
      │   (180k units, 0G Chain pricing)     │
      │                                      │
      │Returns: {breakdown, total%, net%}   │
      └────────┬─────────────────────────────┘
               │
               │ Cost Data (async, <50ms)
               │
               ▼
      ┌──────────────────────────────────────┐
      │FILTER_ENGINE.JS                      │
      │                                      │
      │Step 1: Filter by profit threshold    │
      │  if netProfit% < 3% → REJECT        │
      │                                      │
      │Step 2: Calculate multi-factor score  │
      │  score = profit(30%) +               │
      │          confidence(25%) +           │
      │          liquidity(15%) +            │
      │          risk_inverse(20%) +         │
      │          timeliness(10%)             │
      │  Score: 0-100                        │
      │                                      │
      │Step 3: Filter by score threshold     │
      │  if score < 60 → REJECT             │
      │                                      │
      │Only PASSED opportunities emitted     │
      │                                      │
      │Status: EMITTED (DB update)          │
      └────────┬─────────────────────────────┘
               │
               │ Filtered Opportunities (est. 5-30%)
               │
               ▼
      ┌──────────────────────────────────────┐
      │SIGNAL_EMITTER.JS                     │
      │                                      │
      │For each opportunity:                 │
      │                                      │
      │1. Map DEX names → contract addresses │
      │2. Build InferenceRequest payload:    │
      │   {opp_id, dex_a_addr, dex_b_addr,  │
      │    price_a, price_b, borrow_amt,    │
      │    funding_a, funding_b,             │
      │    timestamp, chain_id}              │
      │3. Validate vs Pydantic schema (Zod)  │
      │4. Queue with p-queue                 │
      │   (concurrency: MAX_CONCURRENT)      │
      │5. POST to TEE inference endpoint     │
      │                                      │
      │On overflow: drop low-score opps,    │
      │            log warning               │
      │                                      │
      │Status: EMITTED (sent)               │
      └────────┬─────────────────────────────┘
               │
               │ HTTP POST (JSON payload, <20ms latency target)
               │
               ▼
      ┌─────────────────────────────────────┐
      │    0G COMPUTE TEE INFERENCE         │
      │                                     │
      │  /infer endpoint receives payload   │
      │  - Attestation validation           │
      │  - Signal verification              │
      │  - Expected profit calculation      │
      │  - Execution recommendation         │
      │                                     │
      │  Response: {decision, profit,       │
      │             risk, confidence,       │
      │             signature}              │
      └────────┬────────────────────────────┘
               │
               ▼
      ┌─────────────────────────────────────┐
      │OPPORTUNITY_DB.JS (SQLite)           │
      │                                     │
      │Persistent logging of all opps:      │
      │                                     │
      │Table: opportunities                 │
      │ • id (PK)                           │
      │ • symbol, dex_a, dex_b              │
      │ • spread%, net_profit%              │
      │ • opportunity_score                 │
      │ • costs breakdown                   │
      │ • status (DETECTED, FILTERED,       │
      │          EMITTED, EXECUTED, etc.)   │
      │ • timestamps (detected, emitted,    │
      │             executed)               │
      │ • realized_profit (post-execution)  │
      │                                     │
      │Analytics queries:                   │
      │ • getPassRate(hours)                │
      │ • getAverageNetProfit(status)       │
      │ • getTopOpportunities(limit)        │
      │ • getStatistics()                   │
      │ • exportToCsv(filters)              │
      └────────┬────────────────────────────┘
               │
               ▼
      ┌─────────────────────────────────────┐
      │  MONITORING DASHBOARD (HTTP)        │
      │                                     │
      │  /analytics endpoint returns:       │
      │  • totalDetected, totalPassed       │
      │  • passRate, avgNetProfit           │
      │  • avgScore, topOpportunities       │
      │  • cost breakdown stats             │
      │  • real-time pipeline health        │
      └─────────────────────────────────────┘
```

## Data Flow & Latency Budgets

All latencies measured from mempool event to emitted signal.

```
Mempool Event (Bloxroute)
    ↓
    ├─ Ingester Processing         [<5ms]   (parse JSON, route event)
    ├─ DEX Price Aggregation        [~0ms]   (in-memory lookup)
    ├─ Opportunity Detection        [10-20ms] (scan 3x3 DEX pairs)
    ├─ Cost Calculation             [20-50ms] (async RPC calls)
    ├─ Filter & Scoring             [<10ms]   (in-memory computation)
    ├─ Signal Packaging & Validation [<5ms]   (JSON building)
    └─ Queue & HTTP Emit           [<20ms]   (p-queue + POST)
    
    TOTAL: ~60-120ms (target <300ms)
```

## Component Details

### 1. **Ingester (ingester.js)**
- **Role**: Main WebSocket connection handler
- **Inputs**: Private mempool provider (Bloxroute, Eden, MEV-Relay)
- **Outputs**: Emitted events (mempool-txs, dex-snapshot, bdn-block)
- **Connection Management**: Exponential backoff (1s→2s→4s→8s→16s→30s)
- **HTTP Endpoints**:
  - `/status` - Connection state, history, metrics
  - `/health` - Simple health check
  - `/metrics` - Message counts and uptime
- **Failure Mode**: Graceful reconnection, no data loss during brief outages

### 2. **DEX Price Feed (dex_price_feed.js)**
- **Role**: Real-time perpetual swap price aggregation
- **Polling Interval**: 500ms
- **DEXs Monitored**: Aave Perps, Hyperliquid, dYdX
- **Stale Price Detection**: Marks prices >2 seconds old as stale, excludes from calcs
- **In-Memory Storage**: Price map with last-update timestamps
- **Failure Mode**: Continues with available DEXs, logs failures for monitoring

### 3. **Opportunity Detector (opportunity_detector.js)**
- **Role**: Continuous scanning for price discrepancies
- **Scan Interval**: 100ms (matches mempool cadence)
- **Spread Threshold**: >0.5% absolute spread
- **Candidate Structure**: UUID, symbol, DEX pair, prices, funding rates, timestamp
- **Mempool Association**: Optionally links with triggering transaction hash
- **Output**: 100-200+ raw candidates per scan cycle (pre-filter)

### 4. **Cost Calculator (cost_calculator.js)**
- **Role**: Precise multi-component cost estimation
- **Components**:
  1. **Flashloan Fee**: 0.09% (from LendingPool.sol)
  2. **Funding Rate Cost**: Hourly charged per 8-hour epoch
  3. **Slippage**: Tiered (0.2% / 0.35% / 0.5% by amount)
  4. **Gas Cost**: 180k units on 0G Chain with ETH/USDC conversion
- **Output**: Complete breakdown, total cost %, net profit %
- **Fallback**: Uses cached/previous gas price if RPC fails

### 5. **Filter Engine (filter_engine.js)**
- **Role**: Opportunity quality & profitability filtering
- **Filters Applied**:
  1. **Profit Threshold**: Reject if netProfit% < 3%
  2. **Score Threshold**: Reject if score < 60 (0-100 scale)
- **Scoring Formula** (weighted sum):
  - Net Profit: 30% (normalized to 0-100)
  - Confidence: 25% (based on spread magnitude)
  - Liquidity: 15% (DEX tier estimate)
  - Risk: 20% (1 - funding rate volatility)
  - Timeliness: 10% (mempool tx association boost)
- **Output**: ~10-30% pass through (depends on market conditions)
- **Status Updates**: Database records all rejections with reason

### 6. **Signal Emitter (signal_emitter.js)**
- **Role**: Package & forward opportunities to TEE inference
- **Validation**: Zod schema validation (mirrors Pydantic)
- **DEX Mapping**: Names → contract addresses on 0G Chain
- **Payload Format**: InferenceRequest (opportunity_id, prices, funding rates, timestamp, chain_id)
- **Queue Management**: p-queue with configurable concurrency (default: 3)
- **Failure Mode**: Queue overflow drops low-scoring opps, logs warning
- **TEE Endpoint**: Configurable via `TEE_INFERENCE_ENDPOINT` env var

### 7. **Simulator (simulator.js)**
- **Role**: Synthetic data generation for dev/testing without live credentials
- **Scenarios**:
  - **High Volatility**: 80% of cycles have opportunities (good for execution testing)
  - **Low Volatility**: 10% of cycles (test filtering aggressiveness)
  - **Network Congestion**: High gas prices, 30% opportunity frequency
  - **Rapid Reversion**: 200ms spread open/close, tests timing logic
- **Parameters**: Configurable spread, funding rate, gas price ranges
- **Same Interface**: Uses same EventEmitter as real ingester for transparent swapping

### 8. **Analytics Database (opportunity_db.js)**
- **Database**: SQLite at `data/opportunities.db`
- **Schema**: Single table with full opportunity lifecycle
- **Status Values**: DETECTED, FILTERED_LOW_PROFIT, FILTERED_LOW_SCORE, EMITTED, SIGNAL_GENERATED, EXECUTED, PROFITABLE, UNPROFITABLE, EXPIRED
- **Query Functions**:
  - `getPassRate(hours)` - Filter effectiveness
  - `getAverageNetProfit(status)` - Profitability benchmarking
  - `getTopOpportunities(limit)` - Best opportunities
  - `getStatistics()` - Comprehensive overview
  - `exportToCsv(filters)` - Post-hackathon analysis
- **Indices**: On status, symbol, detected_at, net_profit for fast queries

## Configuration

### Environment Variables

```bash
# Provider Configuration
MEMPOOL_MODE=live                              # "live" or "simulation"
MEMPOOL_PROVIDER=bloxroute                     # "bloxroute", "eden", "mev-relay"
MEMPOOL_WEBSOCKET_URL=wss://virginia.eth.blxrbdn.com/ws
MEMPOOL_API_KEY=<your_api_key_hex>
MEMPOOL_SUBSCRIPTION_TOPICS=newTxs,pendingTxs,dexSnapshots,bdnBlocks

# Ingestion Parameters
MEMPOOL_BORROW_AMOUNT_USDC=50000
MEMPOOL_MIN_PROFIT_THRESHOLD=3.0
MEMPOOL_POLLING_INTERVAL_MS=100
MEMPOOL_PRICE_REFRESH_MS=500

# TEE Integration
TEE_INFERENCE_ENDPOINT=http://localhost:8000/infer
MAX_CONCURRENT_POSITIONS=3

# Chain Configuration
CHAIN_ID=16600                                 # 0G Chain ID
0G_CHAIN_ID=16600

# DEX Contract Addresses (0G Chain)
AAVE_PERPS_CONTRACT=0x...
HYPERLIQUID_CONTRACT=0x...
DYDX_CONTRACT=0x...

# Database
OPPORTUNITY_DB_PATH=./data/opportunities.db

# RPC
RPC_PROVIDER=https://eth-mainnet.g.alchemy.com/v2/demo
```

## Testing & Validation

### Unit Tests
- **Cost Calculator** (test_cost_calculator.js): 20+ test cases covering all tiers, edge cases
- **Filter Engine** (test_filter_engine.js): Threshold filtering, score weighting, rejection tracking
- **Opportunity Detector** (test_opportunity_detector.js): DEX pair generation, stale prices, candidate structure

### Integration Tests
- **Full Pipeline** (test_ingestion_pipeline.js):
  - 60-second simulation run
  - Assert ≥5 opportunities detected
  - Verify 10-40% pass rate
  - Confirm all emitted opportunities have netProfit% > 3%
  - Database status transitions correct
  - Detector running at correct cadence (100ms)

### Running Tests

```bash
npm test                                        # All tests
npm test -- test_cost_calculator.js             # Single test file
npm test -- --testNamePattern="Flashloan Fee"   # By test name
```

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| Total Pipeline Latency | <300ms | 60-120ms |
| Ingester Processing | <5ms | 2-3ms |
| DEX Price Lookup | <1ms | <1ms |
| Opportunity Detection | 10-20ms | 15ms |
| Cost Calculation | 20-50ms | 35ms |
| Filter & Scoring | <10ms | 5ms |
| Signal Emission | <20ms | 10-15ms |
| Detector Scan Interval | 100ms | 100ms ±10ms |
| DEX Price Poll Interval | 500ms | 500ms ±50ms |

## Monitoring & Debugging

### HTTP Endpoints

```bash
# Ingester status
curl http://localhost:3001/status
curl http://localhost:3001/health
curl http://localhost:3001/metrics

# Expected responses:
# GET /status: {state: "CONNECTED", reconnectAttempt: 0, stateHistory: [...]}
# GET /health: {healthy: true, state: "CONNECTED"}
# GET /metrics: {totalReceived: 1234, totalByType: {...}, uptime: 234.5}
```

### Log Monitoring

All components log with ISO timestamps and structured data:

```
[2026-05-11T10:30:45.123Z] [INGESTER] [INFO] WebSocket connection established
[2026-05-11T10:30:45.156Z] [DEX_PRICE] [DEBUG] Fetched Aave Perps prices {marketsUpdated: 3}
[2026-05-11T10:30:45.234Z] [OPPORTUNITY_DETECTOR] [DEBUG] Detected raw opportunity {id: "...", spread: "2.345%"}
[2026-05-11T10:30:45.289Z] [COST_CALCULATOR] [DEBUG] Calculated total costs {opportunityId: "...", totalCost: "$125.43"}
[2026-05-11T10:30:45.310Z] [FILTER_ENGINE] [INFO] ✓ Opportunity PASSED filter {score: 75, netProfit: "3.25%"}
[2026-05-11T10:30:45.325Z] [SIGNAL_EMITTER] [INFO] ✓ Signal sent to TEE {queueDepth: 2}
```

### Database Queries

```sql
-- Pass rate over last hour
SELECT * FROM opportunities WHERE status='EMITTED' AND detected_at > (strftime('%s', 'now') - 3600);

-- Most profitable opportunities
SELECT * FROM opportunities WHERE status='EXECUTED' ORDER BY realized_profit_usdc DESC LIMIT 10;

-- Cost breakdown analysis
SELECT 
  AVG(flashloan_fee_usdc) as avg_flashloan,
  AVG(slippage_cost_usdc) as avg_slippage,
  AVG(gas_cost_usdc) as avg_gas,
  AVG(total_cost_usdc) as avg_total
FROM opportunities;
```

## Deployment

### Development

```bash
# Simulation mode (no credentials needed)
MEMPOOL_MODE=simulation npm start

# With simulator scenario
MEMPOOL_MODE=simulation MEMPOOL_SIMULATOR_SCENARIO=high_volatility npm start
```

### Production (with Bloxroute)

```bash
# Set credentials in .env
MEMPOOL_MODE=live
MEMPOOL_PROVIDER=bloxroute
MEMPOOL_API_KEY=<your_key>
MEMPOOL_WEBSOCKET_URL=<your_wss_url>

# Start service
npm start

# Monitor health
watch -n 1 'curl -s http://localhost:3001/health | jq'
```

### Docker Deployment

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3001
ENV NODE_ENV=production
CMD ["npm", "start"]
```

## Future Enhancements

1. **Multi-chain Support**: Extend to Arbitrum, Polygon, Optimism
2. **Cross-DEX Opportunities**: Include CEX-DEX spreads
3. **Automated Threshold Tuning**: ML-based profit threshold optimization
4. **Adversarial Filtering**: Detect sandwich/front-run attempts in mempool
5. **Batch Opportunities**: Combine multiple micro-opportunities
6. **MEV Distribution**: Share upside with Bloxroute and relayers
7. **Trustless Attestation**: Integrate attestation framework for validator confidence

---

**Last Updated**: May 11, 2026
**Pipeline Version**: 1.0.0
**Target Network**: 0G Chain (16600)
