# Testnet Validation Methodology (0G Testnet)

Validation Summary: fill after run

Key headline numbers (to appear after session):

- Total trades executed: 
- Settlement rate: 
- Average realized profit per trade (USDC): 
- Net P&L over session (USDC): 
- System uptime: 
- Mainnet deployment verdict: APPROVED / CONDITIONAL / BLOCKED

Every Trade on 0G Explorer

During the session we produce a table of every trade with sequence_number, tx_hash (linked to https://chainscan-galileo.0g.ai/tx/{hash}), realized_profit_usdc, profit_variance_pct, confirmation_latency_ms. The file `docs/testnet_reports/FINAL_REPORT_{session_id}.md` will contain the full table for judge review.

Validation Criteria Evidence

- Criterion A (Settlement Rate): paste counts of confirmed vs reverted transactions.
- Criterion B (Profit Accuracy): distribution of profit variance percentages (ASCII histogram).
- Criterion C (Risk Breakers): list any trades with loss and confirm none exceeded 5%.
- Criterion D (Uptime): hourly uptime log and any restart events.

Parameter Tuning Log

All parameter adjustments made during the session are recorded in `data/testnet_sessions/{session_id}_tuning.jsonl` with the evidence used to make each change.

For Judges

- Verified contract addresses (from deployments/testnet.json) with direct explorer links.
- Representative transactions: include links to 5 transactions demonstrating profitable execution, rejected signals, circuit breaker, and inference latency spike.
- Quick local replay command for mini-session: `python3 scripts/run_testnet_validation.py --target-trades 10 --duration-hours 2`
