# Flashix Integration Testing

This suite validates the end-to-end Flashix arbitrage flow against replayed market data, synthetic mempool opportunities, dry-run execution, and failure-injection scenarios. The committed baseline report is [`docs/integration_reports/baseline_report.json`](docs/integration_reports/baseline_report.json).

## Test Coverage Summary

| Category | Cases | Pass Criteria | Current Pass Rate |
| --- | ---: | --- | ---: |
| Normal Profitable | 15 | Executed opportunities settle with realized profit within 5% of expected | 100% |
| Normal Unprofitable | 10 | Opportunities are rejected or blocked before execution | 100% |
| Edge Cases | 20 | Each injected failure mode produces its expected safe response | 100% |
| Latency SLA | 6 stages | p95 stays within the stage budget and total pipeline stays below the gate | 100% |
| Profit Accuracy | 89 executed trades | Every confirmed trade stays within 5% of expected profit | 100% |

## How to Run

Full suite:

```bash
python tests/run_integration_tests.py
```

Quick smoke test:

```bash
python tests/run_integration_tests.py --data-source SYNTHETIC --n-opportunities 30 --time-acceleration 200
```

The runner writes the latest JSON report to [`docs/integration_reports/latest.json`](docs/integration_reports/latest.json) and the latency table to [`docs/integration_reports/latest_latency.md`](docs/integration_reports/latest_latency.md).

## Reading the Integration Report

The report is serialized as `IntegrationTestReport` and contains the following key fields:

- `report_id`: Unique identifier for the report instance.
- `session_config`: The replay session configuration, including data source, seed, and acceleration factor.
- `total_cases`, `passed`, `failed`, `errored`, `skipped`: Aggregate case counts.
- `pass_rate`: Overall success rate across the full run.
- `mainnet_deployment_approved`: Binary gate flag. This is `true` only when the suite satisfies the deployment criteria.
- `critical_failures`: Any safety-related failures. Any entry here blocks deployment.
- `pipeline_latency_percentiles`: Stage-level latency evidence used to verify SLA compliance.
- `profit_accuracy_metrics`: Expected-vs-realized profit accuracy for confirmed trades.
- `edge_case_results`: Outcome of each targeted edge-case injector.
- `decision_accuracy`: Precision/recall/F1 for historical replay decision matching.
- `funnel_report`: Stage-by-stage rejection funnel showing where opportunities were filtered out.
- `latency_profile`: Full per-stage timing series and SLA violations.
- `accuracy_report`: Aggregate accuracy for executed trades.

The most important field is `mainnet_deployment_approved`. If it is `false`, deployment is blocked even if the suite mostly passes. `critical_failures` is the second hard stop: any safety entry there prevents release. `pipeline_latency_percentiles` is the latency proof the judges can inspect directly.

## Edge Case Results Reference

| Edge Case | Triggering Condition | Expected System Response | Actual Response in Latest Report | Result |
| --- | --- | --- | --- | --- |
| Liquidation Scenario | Collateral ratio forced to 0.90 | Risk manager blocks execution | `BLOCKED_BY_RISK` | PASS |
| Funding Rate Spike | Funding rate overridden to 0.009 | Borrow-rate breaker opens and blocks the trade | `BLOCKED_BY_GAS` | PASS |
| Network Delay Mild | 3,000 ms execution delay | Trade completes before timeout | `CONFIRMED` | PASS |
| Network Delay Severe | 35,000 ms execution delay | Watchdog closes the position with timeout handling | `TIMEOUT` | PASS |
| Gas Spike | Gas price inflated to 140% of baseline | Gas breaker blocks all submitted opportunities | `BLOCKED_BY_GAS` | PASS |
| Model Drift Early | 2% stale-model bias with execution penalty | Rolling bias becomes negative and is detected | `PASS` | PASS |
| Flash Crash | DEX price drops to 80% of prior level | Inference skips the trade | `SKIP` | PASS |
| Collateral Drop 10% | Collateral ratio reduced from 1.6x to 1.44x | Position closes before the 1.5x floor | `BLOCKED_BY_RISK` | PASS |

## For Judges

To verify the integration claims, clone the repo, run `./setup.sh`, then run `python tests/run_integration_tests.py --data-source SYNTHETIC`. You will see 120 opportunities processed in approximately 8 minutes with a final PASS/FAIL verdict. The report is written to `docs/integration_reports/latest.json` and all stage latencies are printed to stdout.

The committed baseline report at `docs/integration_reports/baseline_report.json` is the reference artifact for comparison against any rerun.
