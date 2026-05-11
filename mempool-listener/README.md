# Mempool Listener Module

High-performance Node.js services that ingest private mempool feeds, detect arbitrage opportunities, filter them for profitability, and emit signals to the 0G Compute TEE inference layer.

## Quick Start

### Development (Simulation Mode - No Credentials Needed)

```bash
# Install dependencies
npm install

# Run with synthetic data
MEMPOOL_MODE=simulation npm start
```

### Production (Live Bloxroute Provider)

```bash
# Set credentials in .env (see docs/MEMPOOL_SETUP.md for details)
MEMPOOL_MODE=live
MEMPOOL_PROVIDER=bloxroute
MEMPOOL_API_KEY=<your_api_key>
MEMPOOL_WEBSOCKET_URL=wss://virginia.eth.blxrbdn.com/ws

npm start

# Monitor health
curl http://localhost:3001/health
curl http://localhost:3001/status
curl http://localhost:3001/metrics
```

## Core Components

### 1. **ingester.js** - WebSocket Connection Handler
- Connects to private mempool provider (Bloxroute, Eden Network, MEV-Relay)
- Implements robust connection lifecycle management
- Exponential backoff reconnection (1s → 2s → 4s → 8s → 16s → 30s)
- HTTP endpoints for status monitoring (/status, /health, /metrics)
- Emits events: `mempool-txs`, `dex-snapshot`, `bdn-block`

**Key Functions:**
- `connect()` - Establish WebSocket with auth header
- `scheduleReconnect()` - Implement exponential backoff
- HTTP server on port 3001

**Example Usage:**
```javascript
const { ingesterEmitter } = require('./ingester');

ingesterEmitter.on('mempool-txs', (data) => {
  console.log(`Received ${data.txs.length} transactions`);
});

ingesterEmitter.on('dex-snapshot', (data) => {
  console.log(`DEX liquidity updated at ${data.receivedAt}`);
});
```

---

### 2. **dex_price_feed.js** - Real-Time Price Aggregation
- Polls Aave Perps, Hyperliquid, and dYdX at 500ms intervals
- Maintains in-memory price map with staleness detection
- Prices marked stale if >2 seconds old, excluded from opportunity detection
- Fetches mark price, index price, funding rates, collateral rates

**Key Functions:**
- `startPriceFeed()` - Begin polling all DEXs
- `stopPriceFeed()` - Stop polling
- `getPriceSpread(symbol, dexA, dexB)` - Get spread between DEX pair
- `getPrice(symbol, dex)` - Get single DEX price
- `getAllPrices()` - Get all cached prices

**Example Usage:**
```javascript
const priceFeed = require('./dex_price_feed');

priceFeed.startPriceFeed();

const spread = priceFeed.getPriceSpread('BTC-USD-PERP', 'aave', 'hyperliquid');
if (spread && spread.spreadPercent > 0.5) {
  console.log(`Found ${spread.spreadPercent}% spread`);
}
```

---

### 3. **opportunity_detector.js** - Continuous Opportunity Scanning
- Scans for price discrepancies at 100ms intervals (matches mempool cadence)
- Detects all DEX pair combinations (3 markets × 3 DEX pairs = 9 comparisons per cycle)
- Flags opportunities with spread > 0.5% (minimum viable threshold before costs)
- Emits raw candidates to filter engine
- Logs all detected opportunities to database

**Key Functions:**
- `startDetector()` - Begin 100ms scanning cycles
- `stopDetector()` - Stop detector
- `scanForOpportunities()` - Single scan cycle (called every 100ms)
- `getDetectorStats()` - Current statistics

**Candidate Structure:**
```javascript
{
  id: 'uuid-string',
  symbol: 'BTC-USD-PERP',
  dexA: 'aave',
  dexB: 'hyperliquid',
  dexAPrice: 42000.50,
  dexBPrice: 42210.75,
  grossSpreadPercent: 0.50,
  spreadDirection: 'buy_a_sell_b',
  fundingRateDiff: 0.000015,
  detectedAt: 1715401845123,
  mempoolTxHash: null,
  scanCycleId: 12345
}
```

**Example Usage:**
```javascript
const detector = require('./opportunity_detector');

detector.startDetector();

detector.opportunityEmitter.on('candidate', (candidate) => {
  console.log(`New opportunity: ${candidate.symbol} @ ${candidate.grossSpreadPercent}%`);
});
```

---

### 4. **cost_calculator.js** - Multi-Factor Cost Estimation
- Computes precise costs before filtering:
  1. **Flashloan Fee**: 0.09% (from LendingPool.sol)
  2. **Funding Rate Cost**: Per 8-hour epoch (~3 min holding period)
  3. **Slippage**: Tiered by amount (0.2% / 0.35% / 0.5%)
  4. **Gas Cost**: 180k units on 0G Chain with ETH/USDC conversion
- Returns complete cost breakdown for transparency
- Logs all calculations for post-trade analysis

**Key Functions:**
- `calculateTotalCosts(candidate, borrowAmountUsdc)` - Full cost calculation
- `calculateNetProfit(grossSpread%, totalCost%)` - Net profit computation
- `getSlippageRate(borrowAmountUsdc)` - Lookup slippage tier

**Cost Breakdown:**
```javascript
{
  borrowAmountUsdc: 50000,
  flashloanFee: { percent: 0.09, usdc: 45.00 },
  fundingRateCost: { percent: 0.02, usdc: 10.00 },
  slippageCost: { percent: 0.35, usdc: 175.00 },
  gasCost: { percent: 0.08, usdc: 40.00 },
  totalCostUsdc: 270.00,
  totalCostPercent: 0.54
}
```

**Example Usage:**
```javascript
const costs = require('./cost_calculator');

const breakdown = await costs.calculateTotalCosts(candidate, 50000);
const netProfit = costs.calculateNetProfit(2.5, breakdown.totalCostPercent);

console.log(`Net profit after all costs: ${netProfit}%`);
```

---

### 5. **filter_engine.js** - Opportunity Quality Filtering
- Filters raw candidates through two stages:
  1. **Profit Threshold**: Reject if net profit < 3%
  2. **Score Threshold**: Reject if score < 60 (0-100 scale)
- Calculates multi-factor opportunity score:
  - Net Profit: 30%
  - Confidence: 25% (spread magnitude)
  - Liquidity: 15% (DEX tier)
  - Risk: 20% (1 - funding volatility)
  - Timeliness: 10% (mempool tx association)
- Tracks all rejections and pass rates for monitoring

**Key Functions:**
- `startFilterEngine()` - Subscribe to detector
- `stopFilterEngine()` - Unsubscribe
- `filterCandidate(candidate)` - Process single opportunity
- `getFilterMetrics()` - Current filter stats
- `resetMetrics()` - Clear statistics

**Output (Passed Opportunity):**
```javascript
{
  id: 'uuid-string',
  symbol: 'BTC-USD-PERP',
  dexA: 'aave',
  dexB: 'hyperliquid',
  netProfitPercent: 3.25,
  opportunityScore: 75,
  componentScores: {
    profit: 85,
    confidence: 78,
    liquidity: 72,
    risk: 15,
    timeliness: 100
  },
  status: 'PASSED_FILTER',
  costBreakdown: {...}
}
```

**Example Usage:**
```javascript
const filter = require('./filter_engine');

filter.startFilterEngine();

filter.filteredOpportunityEmitter.on('filtered-opportunity', (opp) => {
  console.log(`✓ Opportunity passed filter: Score=${opp.opportunityScore}, Profit=${opp.netProfitPercent}%`);
});

// Get real-time metrics
const metrics = filter.getFilterMetrics();
console.log(`Pass rate: ${metrics.passRate}%`);
```

---

### 6. **signal_emitter.js** - TEE Inference Integration
- Packages filtered opportunities into InferenceRequest payload
- Validates against Pydantic schema (via Zod)
- Manages concurrent emissions with p-queue (default concurrency: 3)
- Forwards to 0G Compute TEE endpoint via HTTP POST
- Handles queue overflow by dropping low-scoring opportunities

**Key Functions:**
- `startSignalEmitter()` - Subscribe to filter engine
- `stopSignalEmitter()` - Unsubscribe and drain queue
- `emitSignal(opportunity)` - Queue signal for TEE
- `getEmissionMetrics()` - Queue statistics
- `buildInferenceRequest(opportunity)` - Create payload

**Payload Format (sent to TEE):**
```javascript
{
  opportunity_id: 'uuid-string',
  dex_a: '0xaaaa...',      // Contract address on 0G Chain
  dex_b: '0xbbbb...',      // Contract address on 0G Chain
  price_a: 42000.50,
  price_b: 42210.75,
  borrow_amount_usdc: 50000,
  funding_rate_a: 0.000012,
  funding_rate_b: -0.000003,
  timestamp: 1715401845,
  chain_id: 16600
}
```

**Example Usage:**
```javascript
const emitter = require('./signal_emitter');

emitter.startSignalEmitter();

emitter.signalEmitterEventEmitter.on('queue-overflow', (data) => {
  console.warn(`Queue full! Dropped opportunity ${data.opportunityId}`);
});

// Monitor metrics
setInterval(() => {
  const metrics = emitter.getEmissionMetrics();
  console.log(`Emissions: ${metrics.totalSuccessful}/${metrics.totalEmitted}`);
}, 5000);
```

---

### 7. **simulator.js** - Synthetic Data Generation
- Generates realistic synthetic mempool events and DEX prices
- Zero external dependencies - perfect for dev/testing without credentials
- Configurable scenarios: High Volatility, Low Volatility, Network Congestion, Rapid Reversion
- Implements same EventEmitter interface as real ingester

**Scenarios:**
- **high_volatility**: 80% opportunity frequency, spreads up to 6%, good for execution testing
- **low_volatility**: 10% opportunity frequency, small spreads, tests filtering precision
- **network_congestion**: High gas prices (100-200 gwei), most opportunities unprofitable
- **rapid_reversion**: 200ms spread open/close, tests timing logic

**Key Functions:**
- `startSimulator(scenario)` - Begin synthetic generation
- `stopSimulator()` - Stop generation
- `switchScenario(newScenario)` - Change scenario at runtime
- `getSimulatorStatus()` - Current simulation state

**Example Usage:**
```javascript
const simulator = require('./simulator');

// Start with high volatility scenario
simulator.startSimulator(simulator.SCENARIO_TYPES.HIGH_VOLATILITY);

// Same interface as real ingester
const { simulatorEmitter } = simulator;

simulatorEmitter.on('dex-snapshot', (data) => {
  console.log(`Generated ${data.snapshots.length} synthetic price updates`);
});

// Switch scenario during run
setTimeout(() => {
  simulator.switchScenario(simulator.SCENARIO_TYPES.LOW_VOLATILITY);
}, 30000);
```

---

## Configuration

See [docs/MEMPOOL_SETUP.md](../docs/MEMPOOL_SETUP.md) for detailed provider registration and configuration steps.

### Environment Variables

```bash
# Required
MEMPOOL_MODE=live|simulation
MEMPOOL_PROVIDER=bloxroute|eden|mev-relay
MEMPOOL_API_KEY=<your_api_key>
MEMPOOL_WEBSOCKET_URL=wss://...

# Optional (with defaults)
MEMPOOL_BORROW_AMOUNT_USDC=50000
MEMPOOL_MIN_PROFIT_THRESHOLD=3.0
MEMPOOL_POLLING_INTERVAL_MS=100
MEMPOOL_PRICE_REFRESH_MS=500
TEE_INFERENCE_ENDPOINT=http://localhost:8000/infer
MAX_CONCURRENT_POSITIONS=3
CHAIN_ID=16600
```

---

## Testing

```bash
# Run all tests
npm test

# Run unit tests only
npm test -- tests/unit/mempool/

# Run integration tests
npm test -- tests/integration/test_ingestion_pipeline.js

# Run single test
npm test -- test_cost_calculator.js

# Coverage
npm test -- --coverage
```

---

## Architecture

Complete pipeline architecture with latency budgets:

```
Mempool Event [Bloxroute/Eden/MEV-Relay]
    ↓ (0-5ms ingester)
Ingester.js [WebSocket handler]
    ↓ (0ms price lookup)
DEX Price Feed [In-memory map]
    ↓ (10-20ms scan)
Opportunity Detector [100ms intervals]
    ↓ (20-50ms cost calc)
Cost Calculator [Multi-factor costs]
    ↓ (<10ms filter)
Filter Engine [Profit & score thresholds]
    ↓ (<20ms emit)
Signal Emitter [p-queue, validation]
    ↓ (HTTP POST <20ms)
0G Compute TEE Inference
    
TOTAL LATENCY: ~60-120ms (target: <300ms)
```

See [docs/MEMPOOL_ARCHITECTURE.md](../docs/MEMPOOL_ARCHITECTURE.md) for complete architecture diagram and component details.

---

## Monitoring

### HTTP Endpoints (Port 3001)

```bash
# Connection status
curl http://localhost:3001/status
# → {state: "CONNECTED", reconnectAttempt: 0, ...}

# Health check
curl http://localhost:3001/health
# → {healthy: true, state: "CONNECTED"}

# Message metrics
curl http://localhost:3001/metrics
# → {totalReceived: 1234, totalByType: {...}, ...}

# Analytics dashboard
curl http://localhost:3001/analytics
# → {totalDetected: 1500, passRate: 25.3, topOpportunities: [...]}
```

### Logs

All components emit structured JSON logs with ISO timestamps:

```
[2026-05-11T10:30:45.123Z] [INGESTER] [INFO] WebSocket connected
[2026-05-11T10:30:45.234Z] [DEX_PRICE] [DEBUG] Fetched 3 Aave Perps prices
[2026-05-11T10:30:45.345Z] [OPPORTUNITY_DETECTOR] [DEBUG] Detected 12 raw opportunities
[2026-05-11T10:30:45.456Z] [FILTER_ENGINE] [INFO] ✓ Opportunity PASSED filter (Score: 78)
[2026-05-11T10:30:45.567Z] [SIGNAL_EMITTER] [INFO] ✓ Signal sent to TEE (Queue: 2)
```

---

## Performance Targets

| Component | Target Latency | Typical |
|-----------|-----------------|---------|
| Ingester → Event | <5ms | 2-3ms |
| Price Feed | 500ms polling | 500ms ±50ms |
| Detector Scan | 10-20ms | 15ms |
| Cost Calculator | 20-50ms | 35ms |
| Filter + Score | <10ms | 5ms |
| Signal Emission | <20ms | 10-15ms |
| **Total Pipeline** | **<300ms** | **60-120ms** |

---

## Deployment

### Docker

```bash
docker build -t flashix-mempool .
docker run -e MEMPOOL_MODE=live \
           -e MEMPOOL_API_KEY=<key> \
           -p 3001:3001 \
           flashix-mempool
```

### PM2 (Production Process Manager)

```bash
npm install -g pm2
pm2 start npm --name "flashix-mempool" -- start
pm2 monit
pm2 logs flashix-mempool
```

---

## Troubleshooting

### WebSocket Connection Fails
- Check `MEMPOOL_API_KEY` is correctly set (no extra spaces)
- Verify authorization header format in ingester.js
- Ensure firewall allows outbound connections to provider

### No DEX Prices Being Fetched
- Confirm DEX API endpoints are accessible: curl https://aave.com/perps/api/markets
- Check `MEMPOOL_PRICE_REFRESH_MS` interval (default 500ms)
- Verify API response format matches expected schema

### Low Opportunity Detection
- Check market spreads with `getAve

llPrices()` from dex_price_feed
- Verify spread threshold (0.5%) is appropriate for current market conditions
- Review detector stats: `opportunityDetector.getDetectorStats()`

### Filter Rejecting Too Many Opportunities
- Review minimum profit threshold (default 3%) - may be too high
- Check cost calculations with `cost_calculator.calculateTotalCosts()`
- Verify gas price is reasonable: `curl http://localhost:3001/metrics`

---

## References

- [Provider Setup Guide](../docs/MEMPOOL_SETUP.md)
- [Architecture Deep Dive](../docs/MEMPOOL_ARCHITECTURE.md)
- [API Reference](../docs/API_REFERENCE.md)
- [Test Coverage](../tests/)

---

**Version**: 1.0.0
**Last Updated**: May 11, 2026
**Target Network**: 0G Chain (Chain ID: 16600)
