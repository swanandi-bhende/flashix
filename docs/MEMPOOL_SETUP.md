# Private Mempool Data Provider Setup Guide

## Overview
This guide documents how to register with a private mempool data provider and configure WebSocket subscriptions for the flashix arbitrage pipeline. The ingestion pipeline requires access to private mempool events and live DEX liquidity snapshots at 100ms intervals.

## Primary Provider: Bloxroute Elite

### Registration & Onboarding (Est. 10-30 minutes)

**Step 1: Create Account**
- Visit https://bloxroute.com
- Sign up for a developer account or hackathon tier
- Verify email address

**Step 2: Access Dashboard**
- Log into the BDN (Bloxroute Decentralized Network) dashboard
- Navigate to "API Keys" section
- Create a new API key with the following required permissions:
  - `newTxs` - Private mempool transactions
  - `pendingTxs` - Pending transaction pool
  - `bdnBlocks` - Block events with mempool context
  - `dexSnapshots` - DEX liquidity snapshots at 100ms intervals

**Step 3: Obtain Credentials**
After creating your API key, you will receive:
- **WebSocket URL**: `wss://virginia.eth.blxrbdn.com/ws` (for US region; other regions available)
- **API Key Token**: A hex string (store securely in .env)
- **Authorization Format**: Header value as `Authorization: <YOUR_API_KEY>`

**Step 4: Configure .env**
Add these credentials to your `.env` file at the project root:

```bash
# Private Mempool Configuration
MEMPOOL_PROVIDER=bloxroute
MEMPOOL_API_KEY=<your_api_key_hex_string>
MEMPOOL_WEBSOCKET_URL=wss://virginia.eth.blxrbdn.com/ws
MEMPOOL_SUBSCRIPTION_TOPICS=newTxs,pendingTxs,dexSnapshots,bdnBlocks
MEMPOOL_MODE=live  # Set to "simulation" for testing without live credentials

# Mempool Ingestion Parameters
MEMPOOL_BORROW_AMOUNT_USDC=50000
MEMPOOL_MIN_PROFIT_THRESHOLD=3.0
MEMPOOL_POLLING_INTERVAL_MS=100
MEMPOOL_PRICE_REFRESH_MS=500
```

### Pricing & Tier Information

| Tier | Monthly Cost | TPS Limit | Features | Hackathon Suitable |
|------|--------------|-----------|----------|-------------------|
| Starter | $0-99 | 10 | Basic mempool access | ✅ (limited) |
| Developer | $100-499 | 100 | Full mempool + DEX snapshots | ✅ Yes |
| Elite | $500+ | Unlimited | Priority routing + MEV tools | ✅ Premium |

**Recommendation**: Developer or Elite tier for hackathon to ensure 100ms DEX snapshot updates and stable uptime.

### Estimated Provisioning Time
- Account creation: 5 minutes
- API key generation: 2 minutes
- WebSocket credential setup: 3 minutes
- **Total: ~10 minutes**

If credentials expire during the hackathon or need rotation:
1. Log into dashboard
2. Generate new API key
3. Update `MEMPOOL_API_KEY` in `.env`
4. Restart `ingester.js` service
5. Service should reconnect within 30 seconds

---

## Fallback Provider: Eden Network

If Bloxroute is unavailable:

**Registration**: https://api.edennetwork.io
- Similar onboarding process
- WebSocket: `wss://api.edennetwork.io/ws`
- Slightly higher latency (150ms vs 100ms)

---

## Fallback Provider: MEV-Relay

For additional redundancy:

**Registration**: https://mev-relay.flashbots.net
- Restricted to Flashbots-compatible clients
- API endpoint: `https://relay.flashbots.net`
- Requires flashbots-enabled execution layer

---

## Testing Without Live Provider

For development and testing **without live Bloxroute credentials**:

```bash
# Use the simulator mode (no credentials needed)
MEMPOOL_MODE=simulation
MEMPOOL_SIMULATOR_SCENARIO=high_volatility  # See /tests/fixtures/scenarios/
```

This allows full end-to-end testing of the ingestion pipeline with synthetic data.

---

## Troubleshooting

### WebSocket Connection Fails
- Verify `MEMPOOL_API_KEY` is correctly copied (no extra spaces)
- Check that `Authorization` header is included in connection request
- Ensure firewall allows outbound connections to `virginia.eth.blxrbdn.com:443`

### Receiving No DEX Snapshots
- Confirm `dexSnapshots` is in `MEMPOOL_SUBSCRIPTION_TOPICS`
- Some DEXs may require additional subscription parameters
- Check Bloxroute dashboard for subscription status

### High Latency or Missed Events
- Contact Bloxroute support to verify your IP is not rate-limited
- Consider upgrading to higher tier for priority routing
- Verify network connectivity: `ping virginia.eth.blxrbdn.com`

---

## Support & Documentation

- **Bloxroute Docs**: https://docs.bloxroute.com/
- **BDN WebSocket API**: https://docs.bloxroute.com/apis/websocket-api
- **DEX Snapshot Format**: https://docs.bloxroute.com/apis/websocket-api#dex-snapshots
- **Support Email**: support@bloxroute.com

---

## Quick Reset Procedure (if credentials rotate mid-hackathon)

```bash
# 1. Generate new credentials in Bloxroute dashboard
# 2. Update .env
MEMPOOL_API_KEY=<new_key>

# 3. Restart the ingester
pkill -f "node /mempool-listener/ingester.js"
npm start  # or node /mempool-listener/ingester.js

# 4. Verify connection
curl http://localhost:3001/status  # Should show CONNECTED within 30s
```

Estimated re-provisioning time: **< 5 minutes**
