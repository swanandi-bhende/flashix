# Production Runbook — Flashix Mainnet Operations

**Document Version**: 1.0.0  
**Effective Date**: [TBD at deployment]  
**For**: Operations Team, On-Call Engineers, Incident Response

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Daily Operations Checklist](#daily-operations-checklist)
3. [Incident Response Procedures](#incident-response-procedures)
4. [Circuit Breaker Events](#circuit-breaker-events)
5. [Emergency Procedures](#emergency-procedures)
6. [Disaster Recovery](#disaster-recovery)
7. [Monitoring Dashboard](#monitoring-dashboard)

---

## Getting Started

### System Overview

Flashix on mainnet consists of:
- **Agent Service**: Core trading logic, runs continuously
- **Hot Wallet**: Operational key with ≤100 USDC, swept hourly
- **Ramp-Up Engine**: Graduated capital exposure, 6 tiers
- **Kill Switch**: Three channels (RPC, Redis, file sentinel)
- **Market Data**: Oracle-fed pricing and liquidity data
- **TEE Signing**: Cryptographic transaction signing

### Key Files & Locations

```
docs/MAINNET_HARDENING.md           ← Security hardening spec (read first)
docs/PRODUCTION_RUNBOOK.md          ← This file
scripts/start_mainnet_agent.sh       ← Startup script (always run this)
scripts/deploy_mainnet.sh            ← Disabled-by-default future deployment path
data/                                ← Runtime data (sweeps, ramp-up state, events)
data/sweeps.jsonl                    ← Profit sweep audit trail
data/ramp_up_state.json              ← Ramp-up tier and advancement state
data/kill_switch_events.jsonl        ← Kill switch activation log
```

### Emergency Contacts

```
On-Call Engineer: [Phone/Slack]
Ops Lead: [Phone/Email]
Security: [Email]
CEO: [Phone for critical escalation]
```

---

## Daily Operations Checklist

### Morning Standup (Start of Business Day)

**Time**: 09:00 AM UTC  
**Duration**: 5 minutes  
**Responsible**: On-call engineer

#### 1. Health Check (2 minutes)

```bash
# SSH into production server
ssh flashix-mainnet-01

# Check system health
curl http://localhost:8002/pipeline/health | jq '.'
```

Expected output:
```json
{
  "overall": "GREEN",
  "components": {
    "agent": "GREEN",
    "market_data": "GREEN",
    "kill_switch": "ARMED",
    "hot_wallet": "HEALTHY",
    "ramp_up": {"current_tier": 1, "status": "ADVANCING"}
  }
}
```

**Issues to watch for**:
- ❌ Any component is "RED" or "YELLOW" → Investigate immediately (see incident procedures)
- ❌ Kill switch state is not "ARMED" → Investigate (may have been triggered)
- ❌ Hot wallet status is not "HEALTHY" → Check balance and sweep daemon

#### 2. Balance Check (1 minute)

```bash
# Check hot wallet balance
python3 -c "
from agent.security.wallet_manager import HotWalletManager
m = HotWalletManager()
status = m.check_balance()
print(f'Hot wallet: {status.balance_usdc} USDC')
print(f'Sweep required: {status.sweep_required}')
"
```

Expected: `< 100 USDC`, usually `< 20 USDC` after sweep

**Issues to watch for**:
- ❌ Balance > 100 USDC → **Sweep daemon may be stuck** (see "Profit Sweep Failure" incident)
- ⚠️ Balance > 50 USDC and last sweep > 2 hours ago → Check sweep daemon logs

#### 3. Overnight Events Review (2 minutes)

```bash
# Check for circuit breaker events
tail -50 data/circuit_breaker_events.jsonl

# Check for ramp-up advancements
tail -20 data/ramp_up_state.json
```

**Expected events**:
- ✓ Hourly profit sweeps (every 3600 seconds)
- ✓ Regular trades completing (P&L values)
- ✓ Maybe ramp-up tier advancement (if criteria met)

**Issues to watch for**:
- ❌ More than 2 circuit breaker trips → Market conditions may be degrading
- ❌ Lots of trades with P&L < 0 → System may be losing money (escalate)
- ❌ No activity for > 30 minutes → Agent may have crashed

---

### Throughout the Day

**Every Hour** (at :00 minute):
```bash
# Verify sweep completed
stat -f %Sm data/sweeps.jsonl | head -1
```
Should show current hour. If older than 1 hour → **Sweep failure** (page on-call engineer).

**Every 6 Hours**:
```bash
# Check ramp-up advancement progress
python3 -c "
from agent.security.ramp_up_engine import RampUpEngine
engine = RampUpEngine()
status = engine.get_status()
print(f'Tier: {status[\"current_tier\"]}, Can advance: {status[\"can_advance\"]}')
"
```

**Every 24 Hours**:
```bash
# Verify deployment still healthy
curl -s http://localhost:8002/contracts/status | jq '.signalValidator.alive'
```

---

### Evening Shutdown Check (End of Business Day)

**Time**: 18:00 UTC  
**Duration**: 5 minutes

```bash
# Final balance check
python3 scripts/check_wallet_balance.py --address $HOT_WALLET_ADDRESS

# No critical alerts?
tail -5 mainnet_startup_*.log | grep -i error

# System ready for overnight?
curl http://localhost:8002/pipeline/health
```

✓ If all green, system can run unattended overnight.  
❌ If any issues, escalate to on-call engineer for extended shift.

---

## Incident Response Procedures

### Incident Classification

| Severity | Example | Response Time | Action |
|----------|---------|-----------------|--------|
| CRITICAL | Balance > 100 USDC | Immediate | Kill switch, escalate |
| HIGH | Circuit breaker tripped | 5 minutes | Investigate, may rollback |
| MEDIUM | Ramp-up loss detected | 15 minutes | Review, approve reset |
| LOW | Slow transaction confirmation | 1 hour | Monitor, adjust timeout |

---

### Incident 1: Circuit Breaker Tripped

**Symptoms**:
- Trading halted
- New positions not opening
- Log shows: `CIRCUIT_BREAKER_TRIPPED`

**Investigation** (5 minutes):

```bash
# What broke the breaker?
tail -100 data/circuit_breaker_events.jsonl | \
  grep "TRIPPED" | tail -1 | jq '.'
```

Possible causes:
- `LOSS_LIMIT_EXCEEDED`: Daily losses > -500 USDC
- `COLLATERAL_RATIO_LOW`: Ratio < 1.55x
- `GAS_SPIKE`: Gas price > 125% of baseline
- `SLIPPAGE_HIGH`: Trade slippage > 2.0%
- `LIQUIDITY_CRISIS`: Insufficient liquidity on exchanges

**Response**:

**If market-related** (gas spike, liquidity crisis):
1. Wait 30 minutes for conditions to stabilize
2. Manually reset breaker: `python3 scripts/reset_circuit_breaker.py --confirm`
3. Monitor next 10 trades carefully

**If loss-related** (collateral ratio, daily loss):
1. **Do NOT** manually reset (this is a safety feature)
2. Page the trading team lead
3. Investigate what went wrong:
   ```bash
   tail -50 data/trade_records.jsonl | grep "loss"
   ```
4. After root cause analysis, trading lead can approve reset:
   ```bash
   python3 scripts/reset_circuit_breaker.py --confirm --reason "Manual approval after analysis"
   ```

---

### Incident 2: Profit Sweep Failed

**Symptoms**:
- Hot wallet balance > 100 USDC
- Error in logs: `SWEEP_FAILED`
- No sweep.jsonl entry for past 2+ hours

**Investigation** (5 minutes):

```bash
# Check sweep daemon status
ps aux | grep sweep_daemon

# Check recent errors
tail -50 mainnet_startup_*.log | grep -i "sweep"

# Check RPC connectivity
curl -s https://mainnet.0g.ai -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}' | jq '.result'
```

**Common causes**:
1. **RPC unreachable**: API down or network issue
2. **Insufficient gas**: Hot wallet balance too low
3. **Nonce conflict**: Transaction rejected (retry needed)

**Response**:

```bash
# Step 1: Verify RPC is responsive
curl https://mainnet-backup.0g.ai health  # Try backup RPC

# Step 2: Check hot wallet has minimum 5 USDC for gas
python3 -c "
from agent.security.wallet_manager import HotWalletManager
m = HotWalletManager()
status = m.check_balance()
if status.balance_usdc < 5:
    print('ERROR: Hot wallet below 5 USDC minimum')
"

# Step 3: Manually trigger sweep
python3 -c "
from agent.security.wallet_manager import HotWalletManager
m = HotWalletManager()
result = m.sweep_to_cold_storage()
print(f'Sweep result: {result}')
"

# Step 4: Monitor for success
watch -n 2 'tail -1 data/sweeps.jsonl'
```

**If sweep still failing after 2 hours**:
1. **CRITICAL**: Trigger kill switch to halt trading
2. Escalate to ops lead
3. Investigate RPC/network issues with infrastructure team
4. Consider manual wallet transfer if RPC remains down

---

### Incident 3: Ramp-Up Loss Detected

**Symptoms**:
- Log: `RAMP_UP_LOSS_DETECTED`
- Advancement paused
- Ops webhook received

**What happened**:
- A trade at current tier resulted in a loss
- System automatically paused tier advancement (safety feature)
- Ops team is notified to review

**Investigation** (15 minutes):

```bash
# What was the losing trade?
tail -100 data/trade_records.jsonl | grep loss | tail -1 | jq '.'

# What is the current tier state?
cat data/ramp_up_state.json | jq '.current_tier, .zero_losses_at_tier'

# How much loss was it?
tail -100 data/trade_records.jsonl | jq '[.[] | select(.profit_usdc < 0)] | add'
```

**Decision Tree**:

```
Was the loss due to expected slippage?
├─ YES: Market volatility, acceptable risk
│   └─ Approve reset: python3 scripts/ramp_up_reset.py --confirm
│
└─ NO: Unexpected behavior, investigate further
    ├─ Check collateral ratio change
    ├─ Review market data for anomalies
    └─ Decide: Continue with reset OR Rollback tier
```

**Manual Tier Reset**:
```bash
# After reviewing and approving
python3 -c "
from agent.security.ramp_up_engine import RampUpEngine
engine = RampUpEngine()
engine.reset_zero_losses_flag()
print('Tier advancement re-enabled')
"
```

**Manual Tier Rollback** (if market conditions degrading):
```bash
python3 -c "
from agent.security.ramp_up_engine import RampUpEngine
engine = RampUpEngine()
engine.force_rollback(n_tiers=1)  # Go from tier N to N-1
print('Rollback complete')
"
```

---

### Incident 4: Kill Switch Triggered

**Symptoms**:
- Trading halted
- No new positions being opened
- Log: `KILL_SWITCH_ACTIVATED`
- HTTP 503 from pipeline health endpoint

**Possible causes**:
1. Manual trigger by engineer (via RPC, Redis, or file)
2. Automatic trigger from security event (rare)
3. Accidental trigger (test channel not intended)

**Investigation** (2 minutes):

```bash
# Who triggered it and when?
tail -20 data/kill_switch_events.jsonl | jq '.method, .timestamp'

# Was it intentional?
# → Check with team lead / on-call engineer
```

**Recovery**:

**If intentional** (e.g., testing, or deliberate market halt):
1. Resolve the underlying issue
2. Run startup sequence: `bash scripts/start_mainnet_agent.sh`
3. System re-initializes, kill switch re-arms

**If unintentional**:
1. Identify who triggered it and why
2. Understand if there was a real issue that triggered it
3. If false alarm: Just re-start with `bash scripts/start_mainnet_agent.sh`
4. If there was a real issue: Fix issue first, then re-start

---

## Circuit Breaker Events

### What Triggers Circuit Breakers?

Each breaker monitors a specific risk:

| Breaker | Triggers When | Action |
|---------|-----------------|--------|
| DAILY_LOSS | Cumulative P&L < -500 USDC | Halt trading for 24 hours |
| COLLATERAL | Ratio < 1.55x | Close positions immediately |
| SLIPPAGE | Trade slippage > 2.0% | Skip trade, don't execute |
| GAS_SPIKE | Gas > baseline * 1.25 | Delay execution, retry later |
| LIQUIDATION | Ratio approaching 1.5x | Force-close largest positions |

### Reviewing Circuit Breaker Events

```bash
# Last 10 breaker events
tail -10 data/circuit_breaker_events.jsonl | jq '.[] | {time, reason, action}'

# Breakers tripped today
grep "$(date +%Y-%m-%d)" data/circuit_breaker_events.jsonl | wc -l

# Worst breach (most severe)
tail -100 data/circuit_breaker_events.jsonl | \
  jq -s 'sort_by(.severity) | reverse | .[0]'
```

### Normal vs. Abnormal Patterns

**NORMAL** (expected during operation):
- 0-2 GAS_SPIKE events per day (brief, resolves automatically)
- 0-1 SLIPPAGE events per day (high-volatility periods)
- Maybe 1 COLLATERAL warning per week (during market stress)

**ABNORMAL** (investigate immediately):
- More than 3 breaker events in 1 hour
- Any DAILY_LOSS or LIQUIDATION events
- Same breaker triggered repeatedly (indicates systematic issue)

---

## Emergency Procedures

### Emergency Kill Switch Activation

**Use this if**:
- System is misbehaving and needs immediate halt
- Market conditions are severe and dangerous
- Any urgent safety concern

**Methods** (pick any one, all work equally):

**Method 1: RPC Endpoint** (fastest, requires network)
```bash
curl -X POST http://localhost:8099/admin/kill-switch \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

**Method 2: Redis** (if local RPC fails)
```bash
redis-cli PUBLISH flashix:kill-switch halt
```

**Method 3: File Sentinel** (if network completely down)
```bash
touch /tmp/flashix_kill_switch
```

**Verification**:
```bash
# Should see immediate halt
tail -1 data/kill_switch_events.jsonl
curl http://localhost:8002/pipeline/health  # Should be ERROR
```

### Emergency Shutdown

**If system cannot be recovered normally**:

```bash
# Kill all Flashix processes
pkill -f "flashix\|agent\|pipeline"

# Disable auto-restart
systemctl disable flashix-agent

# Check nothing is running
ps aux | grep flashix
# (should show no results)
```

**Recovery**:
- Fix underlying issue
- Run startup sequence: `bash scripts/start_mainnet_agent.sh`
- Re-enable auto-restart: `systemctl enable flashix-agent`

---

## Disaster Recovery

### Database Corruption

**Symptoms**:
- JSON parsing errors in data files
- Ramp-up state corrupted
- Trade records unreadable

**Recovery**:

```bash
# Step 1: Stop the agent
bash scripts/emergency_shutdown.sh

# Step 2: Backup corrupted files
cp data/ramp_up_state.json data/ramp_up_state.json.corrupt.$(date +%s)

# Step 3: Reconstruct from blockchain
python3 scripts/reconstruct_state_from_chain.py \
  --contracts deployments/mainnet.json \
  --output-dir data/

# Step 4: Restart
bash scripts/start_mainnet_agent.sh
```

### Future Release Path (paused)

**Release remains paused by default. Do not roll out unless the release process explicitly re-enables the release placeholder and the team has approved a new release window.**

The approved path forward is:
1. Stop the agent and preserve logs.
2. Complete the security audit and dress rehearsal review.
3. Obtain explicit release approval.
4. Re-enable the release placeholder only in the release window.
5. Use the approved release window checklist before any future rollout.

### RPC Provider Failure

**If primary RPC is down**:

```bash
# Step 1: Switch to backup RPC
export MAINNET_RPC_URL="https://mainnet-backup.0g.ai"

# Step 2: Restart agent
bash scripts/start_mainnet_agent.sh

# Step 3: Verify health
curl http://localhost:8002/pipeline/health
```

**If both RPCs are down**:
1. This is a network-wide issue (not Flashix-specific)
2. System will automatically halt (safety feature)
3. Wait for RPC providers to recover
4. Restart with working RPC URL

---

## Monitoring Dashboard

### Key Metrics to Monitor

```
Real-time Dashboard (refresh every 60 seconds):
├─ System Status: [GREEN/YELLOW/RED]
├─ Hot Wallet: $XX.XX USDC (max 100)
├─ Ramp-Up Tier: N/6 (capital: $X,XXX)
├─ Trades Today: N (P&L: $+XX.XX)
├─ Circuit Breakers: [Status]
├─ Kill Switch: [ARMED/TRIGGERED]
└─ Last Sweep: N minutes ago

Alerts (trigger pages to on-call engineer):
├─ Hot wallet > 100 USDC
├─ Sweep failed (no sweep > 2 hours)
├─ Circuit breaker tripped > 3x in 1 hour
├─ Kill switch triggered
└─ Health check failed
```

### Log Files to Monitor

```bash
# Real-time log tailing
tail -f mainnet_startup_*.log

# Structured event log
tail -f data/circuit_breaker_events.jsonl

# Sweeps audit trail
tail -f data/sweeps.jsonl

# Ramp-up state changes
tail -f data/ramp_up_state.json

# Kill switch events
tail -f data/kill_switch_events.jsonl
```

### Alerting Setup

**Recommended**:
1. Set up log aggregation (ELK Stack or similar)
2. Alert on ERROR/CRITICAL log lines
3. Alert on missing sweeps (> 2 hours without entry)
4. Alert on circuit breaker trips (> 1 per hour)
5. Alert on kill switch activation

---

## Escalation Path

```
ISSUE DETECTED
    ↓
On-Call Engineer Reviews (5 min)
    ├─ Can resolve? → Fix and monitor
    └─ Cannot resolve → Escalate
        ↓
    Ops Lead Reviews (15 min)
    ├─ Can resolve? → Fix and monitor
    └─ Cannot resolve → Escalate
        ↓
    Trading Lead + Security Lead (30 min)
    ├─ System degradation? → Reduce capital
    ├─ Security issue? → Kill switch
    └─ Cannot resolve → Escalate
        ↓
    CEO (Emergency authority)
    ├─ Severe issue? → Shut down system
    └─ Resolve as needed
```

---

## Support & Resources

**Slack Channels**:
- `#flashix-mainnet-ops`: Daily standup, incident discussion
- `#flashix-trading`: Trading decisions, ramp-up approvals
- `#flashix-security`: Security events, audit updates

**Documentation**:
- [MAINNET_HARDENING.md](MAINNET_HARDENING.md): Security specification
- [agent/README.md](../agent/README.md): Agent architecture
- [contracts/README.md](../contracts/README.md): Contract details

**Emergency Number**: [TBD - after deployment]

---

*Last Updated*: [TBD at deployment]  
*Version*: 1.0.0  
*Maintained by*: Flashix Operations Team
