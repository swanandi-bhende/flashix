# Flashix Monitoring

## Metric Taxonomy

| Name | Type | Threshold | Alert Severity |
| --- | --- | --- | --- |
| `OPPS_DETECTED_PER_MIN` | RATE | n/a | INFO |
| `SIGNALS_GENERATED_PER_HOUR` | RATE | n/a | INFO |
| `EXECUTION_SUCCESS_RATE` | RATIO | `< 90%` | CRITICAL |
| `AVG_LATENCY_MEMPOOL_TO_DECISION_MS` | HISTOGRAM | n/a | INFO |
| `AVG_LATENCY_DECISION_TO_SETTLEMENT_MS` | HISTOGRAM | n/a | INFO |
| `AVG_LATENCY_END_TO_END_MS` | HISTOGRAM | n/a | INFO |
| `PROFIT_PER_TRADE_USDC` | GAUGE | n/a | INFO |
| `SHARPE_RATIO_ANNUALIZED` | RATIO | n/a | INFO |
| `WIN_RATE_PCT` | RATIO | n/a | INFO |
| `TOTAL_REALIZED_PNL_USDC` | GAUGE | n/a | INFO |
| `INFERENCE_LATENCY_P50_MS` | HISTOGRAM | n/a | INFO |
| `INFERENCE_LATENCY_P95_MS` | HISTOGRAM | `> 1500 ms` warning, `> 3000 ms` critical | WARNING / CRITICAL |
| `MEMPOOL_DATA_FRESHNESS_MS` | GAUGE | `> 800 ms` | WARNING |
| `AGENT_DECISION_TIME_MS` | GAUGE | n/a | INFO |
| `BLOCK_TIME_MS` | GAUGE | n/a | INFO |
| `GAS_PRICE_GWEI` | GAUGE | n/a | INFO |
| `GAS_PRICE_TREND_PCT` | RATE | `> 25%` spike | WARNING |
| `ORACLE_SOURCE_COUNT` | COUNTER | n/a | INFO |
| `REDIS_QUEUE_DEPTH_MAX` | GAUGE | `> 50` | WARNING |
| `PIPELINE_SLA_BREACHES_PER_HOUR` | RATE | n/a | INFO |
| `CONCURRENT_POSITIONS` | GAUGE | `> 3` | WARNING |
| `COLLATERAL_RATIO` | GAUGE | n/a | INFO |
| `DAILY_PNL_USDC` | GAUGE | `< -25 USDC` | WARNING |
| `DRAWDOWN_FROM_PEAK_PCT` | GAUGE | `> 15%` warning, `> 30%` emergency | WARNING / EMERGENCY |
| `DAILY_LOSS_CAP_UTILIZATION_PCT` | RATIO | n/a | INFO |
| `OPEN_CIRCUIT_BREAKERS_COUNT` | GAUGE | `>= 3` critical | CRITICAL |
| `PORTFOLIO_HEAT` | GAUGE | n/a | INFO |

## Live Dashboard Snapshot

```text
FLASHIX LIVE MONITOR — 2026-05-12 12:00:00 UTC

Execution
opportunities/min               12.50
success_rate                    92.00%
avg_latency_ms                1420.00
profit_per_trade                 6.84
sharpe_ratio                    1.74

Health
inference_p95_ms             1280.00
mempool_freshness_ms          420.00
gas_price_gwei                 18.30
queue_depth                     14.00
open_breakers                    0.00

Risk
concurrent_positions             2.00 / 3
daily_pnl                       31.20
drawdown_pct                     4.10
portfolio_heat                   0.42
```

## Grafana Cloud Setup

1. Run Flashix with `METRICS_PROMETHEUS_ENABLED=true` so the exporter listens on `http://localhost:9090/metrics`.
2. In Grafana Cloud, add a Prometheus data source and point it at the Flashix scrape endpoint through your agent, tunnel, or local forwarder.
3. Import the Flashix dashboard panels and verify the series `flashix_execution_success_rate`, `flashix_daily_pnl_usdc`, and `flashix_drawdown_pct` are visible.

## Slack Webhook Payload

Flashix posts alerts as JSON:

```json
{
  "alert_id": "string",
  "severity": "INFO|WARNING|CRITICAL|EMERGENCY",
  "metric_name": "EXECUTION_SUCCESS_RATE",
  "current_value": 0.81,
  "threshold": 0.90,
  "message": "Execution success rate 81.8% below threshold 90.0% — investigate immediately",
  "triggered_at_iso": "2026-05-12T12:00:00Z",
  "system": "Flashix",
  "environment": "testnet"
}
```

## For Judges

Use these exact URLs during the demo:

1. Overall health: `GET http://localhost:8005/system/health`

```bash
curl http://localhost:8005/system/health
```

2. P&L summary: `GET http://localhost:8005/metrics/financial`

```bash
curl http://localhost:8005/metrics/financial
```

3. Active investigations: `GET http://localhost:8005/alerts/active`

```bash
curl http://localhost:8005/alerts/active
```
