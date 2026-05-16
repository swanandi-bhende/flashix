# Flashix

Autonomous TEE-sealed AI agent that detects, validates, and executes flashloan-funded arbitrage across global DEXs using private mempool ingestion, sealed inference, and on-chain settlement.

## Live Demo

Open the deployed app here: [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/)

The deployed UI mirrors the local dashboard, opportunity queue, risk center, execution flow, settlement views, and compute proofs. Use the demo link for the fastest walkthrough, or run the app locally if you want to inspect logs and source behavior.

## Documentation

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

## Deployed Contracts

- **Testnet (Galileo, chainId 16602):**
	- SignalValidator: 0xEc238754ffb9a846Ba52718D0a78E72878747702 — https://chainscan-galileo.0g.ai/address/0xEc238754ffb9a846Ba52718D0a78E72878747702
	- LendingPool: 0xCe233f627834e017097feFB53f4dfD2085A9B988 — https://chainscan-galileo.0g.ai/address/0xCe233f627834e017097feFB53f4dfD2085A9B988
	- ArbitrageExecutorV2: 0x83c0d423c623F676770D0539acC69e49A2a64ab9 — https://chainscan-galileo.0g.ai/address/0x83c0d423c623F676770D0539acC69e49A2a64ab9
	- TEE / Deployer: 0x28FB61Dc27a37091f53C0c37b5026AdBbF5E1F46

- **Mainnet (aristotle, chainId 16661):**
	- SignalValidator: 0x545CD17d890455040593e35018216C906221c371 — https://chainscan.0g.ai/address/0x545cd17d890455040593e35018216c906221c371
	- LendingPool: 0x4c580Fb35fBcc2A6D7223984B634ccE7EbE730Ed — https://chainscan.0g.ai/address/0x4c580fb35fbcc2a6d7223984b634cce7ebe730ed
	- ArbitrageExecutor: 0x8A22F9af206fCC38d00c44DCa8B15555785b8a4a — https://chainscan.0g.ai/address/0x8a22f9af206fcc38d00c44dca8b15555785b8a4a

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


