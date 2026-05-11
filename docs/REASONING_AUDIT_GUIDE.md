# Reasoning Audit Guide

This guide is for judges who want to inspect how Flashix decided on a trade.
No special setup is required beyond a browser and `curl`.

## Quick Audit in 3 Steps

1. Visit `GET /traces?limit=5&decision=APPROVE` on the live demo server to see the five most recent approved trades.
2. Copy any `opportunity_id` and visit `GET /traces/{opportunity_id}` to read the complete five-section reasoning chain.
3. Visit `GET /traces/{opportunity_id}/verify` to confirm the reasoning arithmetic was internally consistent.

## Sample Reasoning Trace

A good trace reads like a compact audit log with explicit numbers and plain English narrative.

- Opportunity Analysis: `Signal shows 4.2% price discrepancy between Hyperliquid (long at $43,210.50) and dYdX (short at $43,028.20). Borrow amount: $10,000 USDC.`
- Cost Breakdown: `Flashloan fee: 0.09% = $9.00. Slippage: 0.20% = $20.00. Collateral cost: $0.63. Gas: $3.20. Total cost: 0.33% = $32.83.`
- Profit Calculation: `Gross spread: 4.2%. Total cost: 0.33%. Net profit: 3.87% = $387.17.`
- Risk Assessment: `VIX-equivalent: 28/100 (LOW). Funding rate volatility: LOW. Execution risk: LOW. No adverse risk factors detected.`
- Final Decision: `APPROVE execution. Expected profit after gas: $383.97. Expected execution time: 8 seconds.`

## What Makes a Good Reasoning Trace

Judges should check for the following:

- Internally consistent arithmetic across the spread, cost, and profit sections.
- All five sections present in the expected order.
- Risk factors explicitly named when risk is elevated.
- Decision criteria explicitly checked before approval.
- Narrative written in plain English, with parseable JSON underneath.

## Curl Cheat Sheet

```bash
curl "http://localhost:8001/traces?limit=5&decision=APPROVE"
curl "http://localhost:8001/traces/opp_20260511_001"
curl "http://localhost:8001/traces/opp_20260511_001/verify"
curl "http://localhost:8001/traces/stats"
```
