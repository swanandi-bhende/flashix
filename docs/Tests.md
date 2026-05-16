# Tests

Flashix testing covers the full stack: inference determinism, mempool filtering, agent reasoning, contract safety, settlement, replay validation, and end-to-end demo reproducibility.

## Test Suite Map

### Root-Level Test Entrypoints

- [tests/integration_test.py](../tests/integration_test.py) runs the broad Python integration pass used as the repo-level sanity check.
- [tests/readme.test.js](../tests/readme.test.js) checks repository documentation or README-linked expectations.
- [tests/run_integration_tests.py](../tests/run_integration_tests.py) orchestrates the wider integration test flow from a single command.

### Unit Tests

#### Compute

- [tests/unit/compute/test_determinism.py](../tests/unit/compute/test_determinism.py) checks that inference and signal outputs stay deterministic for the same input.

#### Mempool

- [tests/unit/mempool/test_filter_engine.js](../tests/unit/mempool/test_filter_engine.js) verifies the filtering logic that decides whether a raw opportunity should move forward.
- [tests/unit/mempool/test_cost_calculator.js](../tests/unit/mempool/test_cost_calculator.js) checks fee, gas, and execution-cost calculations used to decide profitability.
- [tests/unit/mempool/test_opportunity_detector.js](../tests/unit/mempool/test_opportunity_detector.js) validates the opportunity detection logic that turns market activity into candidate trades.

#### Risk

- [tests/unit/risk/test_portfolio_limits.py](../tests/unit/risk/test_portfolio_limits.py) validates portfolio limit enforcement such as loss caps, collateral constraints, and exposure thresholds.
- [tests/unit/risk/test_gas_circuit_breaker.py](../tests/unit/risk/test_gas_circuit_breaker.py) checks the breaker that pauses trading when gas conditions become too expensive or unstable.
- [tests/unit/risk/test_position_watchdog.py](../tests/unit/risk/test_position_watchdog.py) exercises the watchdog that watches open positions and flags unsafe states.

- [tests/unit/test_placeholder.py](../tests/unit/test_placeholder.py) is a placeholder hook for additional unit coverage and keeps the unit tree importable.

### Agent Tests

- [agent/tests/test_gemini_connection.py](../agent/tests/test_gemini_connection.py) verifies that the reasoning layer can connect to the configured Gemini provider.
- [agent/tests/run_tests.py](../agent/tests/run_tests.py) is the agent-side test runner used to exercise agent-specific checks in one pass.
- [agent/tests/mock_signal_generator.py](../agent/tests/mock_signal_generator.py) provides deterministic sample signals for agent and reasoning tests.

### Contract Tests

- [contracts/tests/SignalValidator.test.ts](../contracts/tests/SignalValidator.test.ts) checks trusted-signer verification, replay protection, and signal expiry handling.
- [contracts/tests/LendingPool.test.ts](../contracts/tests/LendingPool.test.ts) validates flashloan availability, repayment enforcement, and pool fee accounting.
- [contracts/tests/ArbitrageExecutor.test.ts](../contracts/tests/ArbitrageExecutor.test.ts) exercises the execution flow that consumes a verified signal and completes the flashloan trade path.
- [contracts/tests/GasProfile.test.ts](../contracts/tests/GasProfile.test.ts) measures gas usage and helps keep the execution path within expected cost bounds.
- [contracts/tests/GasOptimization.test.ts](../contracts/tests/GasOptimization.test.ts) checks the contract-side optimizations that keep deployment and execution gas lower.

### Integration Tests

- [tests/integration/test_agent_pipeline.py](../tests/integration/test_agent_pipeline.py) checks the handoff from filtered opportunity to agent decision.
- [tests/integration/test_crypto_chain.py](../tests/integration/test_crypto_chain.py) validates the end-to-end cryptographic chain across compute, signing, and verification.
- [tests/integration/test_execution_engine.py](../tests/integration/test_execution_engine.py) exercises the execution engine path from approval to broadcast and outcome handling.
- [tests/integration/test_full_pipeline.py](../tests/integration/test_full_pipeline.py) runs the full discovery-to-settlement pipeline in one pass.
- [tests/integration/test_ingestion_pipeline.js](../tests/integration/test_ingestion_pipeline.js) verifies the mempool ingestion path that feeds the opportunity pipeline.
- [tests/integration/test_market_data_pipeline.py](../tests/integration/test_market_data_pipeline.py) checks market data freshness, source health, and feed trust logic.
- [tests/integration/test_metrics_pipeline.py](../tests/integration/test_metrics_pipeline.py) confirms the operational metrics pipeline continues to collect and expose the expected signals.
- [tests/integration/test_risk_manager.py](../tests/integration/test_risk_manager.py) validates that the live risk manager enforces breaker and exposure behavior across the workflow.
- [tests/integration/test_settlement_monitor.py](../tests/integration/test_settlement_monitor.py) checks that settlements, repayments, and ledger state are monitored correctly.
- [tests/integration/test_tee_inference.py](../tests/integration/test_tee_inference.py) verifies the TEE-backed inference path and the link between inference output and downstream consumers.

### Replay And Validation

- [tests/replay/test_case_generator.py](../tests/replay/test_case_generator.py) generates deterministic replay cases so inference and decision changes can be reproduced.
- [tests/replay/extreme_scenario_tests.py](../tests/replay/extreme_scenario_tests.py) exercises edge-case and stress scenarios to catch failures that do not appear in the happy path.
- [tests/validation/end_to_end_accuracy.py](../tests/validation/end_to_end_accuracy.py) measures whether the system still produces the expected output across the entire flow.
- [tests/validation/latency_profiler.py](../tests/validation/latency_profiler.py) profiles stage-by-stage latency so performance regressions are visible.

## Run Tests

Frontend:

```bash
npm --prefix frontend test
```

Backend and compute:

```bash
source .venv/bin/activate
pytest -q
```

Contracts:

```bash
cd contracts
npx hardhat test
```

Replay and validation:

```bash
python -m pytest tests/replay/ -v
python -m pytest tests/validation/ -v
python tests/run_integration_tests.py
```

## What To Verify

- Signal encoding stays stable across Python and Solidity.
- The compute signature verifier recovers the expected signer and the replay suite stays deterministic.
- The agent never bypasses the approval gate or changes a decision without a trace update.
- The mempool filters reject weak opportunities and cost calculations stay consistent.
- The flashloan path repays principal and fee atomically.
- Settlement reports match the executed trade outcome.
- The risk manager and circuit breakers fire when the configured limits are exceeded.
- The UI demo reproduces the seeded opportunity path and the integration suite still links every stage together.

## Performance And Reproducibility

- The smoke script reproduces the core demo in about 10 minutes locally.
- The replay harness is the right check for inference changes before deployment.
- The validation suite is the right place to look when you want latency and end-to-end accuracy numbers.
- Integration reports and validation reports should be kept in the docs artifacts folders for judge review.

