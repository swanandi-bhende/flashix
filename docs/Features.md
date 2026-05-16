# Features

Flashix combines sealed inference, private mempool ingestion, and atomic execution into a single audit-friendly arbitrage stack.

## Core Features

- TEE-sealed decision making through 0G Compute and the compute verification chain.
- Private mempool ingestion with live or simulation modes.
- Opportunity ranking using spread, cost, freshness, and risk checks.
- Mandatory approval gates before execution.
- Flashloan-based atomic execution with no partial settlement state.
- On-chain replay protection and proof emission.
- Settlement exports and post-trade audit trails.
- Human override and circuit breaker controls.
- Replayable demo state for judges and operators.

## Operator Experience

- Dashboard exposes health, actions, and demo controls.
- Opportunities shows the queue and its decision trail.
- Risk shows breaker state, exposure, and overrides.
- Execution shows simulation, gas, broadcast, and proof links.
- Settlement shows realized PnL and outstanding obligations.
- Compute shows the sealed proof chain and signature validation.

## Safety Features

- Simulation-before-broadcast.
- Stale-signal rejection.
- Replay protection on signal IDs.
- Router allowlisting.
- Profit threshold checks.
- Rate, gas, and freshness thresholds.
- Explicit user approval when the workflow requires it.

## Evidence And Auditability

- Append-only logs for decisions and post-trade outcomes.
- Exportable ledger records.
- On-chain events for execution proof.
- Persisted demo artifacts for replay and verification.

## Where The Code Lives

- Frontend: `frontend/src/`.
- Agent: `agent/` and `agent/prompts/`.
- Compute: `compute/`.
- Mempool pipeline: `mempool-listener/`.
- Contracts: `contracts/`.
- Supporting docs: `docs/`.
