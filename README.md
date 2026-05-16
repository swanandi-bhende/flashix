# Flashix

Autonomous TEE-sealed AI agent that detects, validates, and executes flashloan-funded arbitrage across global DEXs using private mempool ingestion, sealed inference, and on-chain settlement.

## Live Demo

Open the deployed app here: [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/)

The deployed UI mirrors the local dashboard, opportunity queue, risk center, execution flow, settlement views, and compute proofs. Use the demo link for the fastest walkthrough, or run the app locally if you want to inspect logs and source behavior.

## Documentation

- [Docs Index](docs/README.md)
- [Setup Guide](docs/Setup.md)
- [Interactive Demo Guide](docs/Demo.md)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [0G Compute](docs/0G_Compute.md)
- [0G Implementation](docs/0G_Implementation.md)
- [Deploy](docs/Deploy.md)
- [Features](docs/Features.md)
- [Security](docs/Security.md)
- [Tests and Verification](docs/Tests.md)
- [Troubleshooting](docs/Troubleshooting.md)

## What Flashix Does

Flashix is built around a simple but strict pipeline:

1. Ingest private or near-real-time market and mempool signals.
2. Rank opportunities with deterministic filters, cost checks, and risk limits.
3. Send the request through sealed compute / reasoning so sensitive inputs are not exposed unnecessarily.
4. Approve or reject candidates in the opportunities queue.
5. Simulate execution before broadcast.
6. Broadcast the winning trade and record settlement evidence.
7. Persist the lifecycle so operators can audit every step later.

The UI exposes that flow directly through the following pages:

- Dashboard: system overview, health metrics, and demo launch controls.
- Pipeline: lifecycle stages and playback of the seeded demo item.
- Opportunities: live queue with simulate, approve, reject, and trace actions.
- Risk: breakers, overrides, and position-level risk controls.
- Execution: pre-flight simulation, gas analysis, on-chain broadcast, and proof links.
- Settlement: realized and unrealized PnL, open positions, repayment tracking, and exports.
- Market Data: oracle health, freshness, and fallback reliability.
- Compute: TEE proof inspection, signature verification, and linked traces.

## Quick Start

```bash
git clone https://github.com/swanandi-bhende/flashix.git
cd flashix
./setup.sh
```

If you prefer the manual path:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cd frontend
npm install
cd ..
```

Start the local services:

```bash
python3 scripts/tee_service.py
source .venv/bin/activate
python -m agent.backend_app
npm --prefix frontend run dev
```

Then open the deployed app at [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/) or the local frontend URL printed by Vite.

## Development Commands

```bash
npm run mempool:listen
./scripts/start_agent.sh
./scripts/run_tests.sh
./scripts/health_check.sh
```

For contract workflows:

```bash
cd contracts
npx hardhat compile
npx hardhat test
npx hardhat coverage
```


## Project Notes

- Flashix uses a consolidated FastAPI backend in `agent/backend_app.py`.
- The React frontend routes are defined in `frontend/src/router.tsx`.
- The dashboard is the best entry point for understanding the system state.
- The `Compute` and `Execution` pages contain the strongest proof artifacts for demo review.


