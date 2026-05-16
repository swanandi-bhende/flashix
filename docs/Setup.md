# Setup

This guide covers the full local development flow for Flashix, from environment preparation to running the demo UI and supporting services.

## Supported Environments

- macOS
- Linux
- WSL2 on Windows
- Python 3.12 or higher
- Node.js 18 or 20
- Git

## What You Need Before You Start

Make sure the following commands work on your machine:

```bash
python3 --version
node --version
npm --version
git --version
```

If Python or Node is missing, install them before continuing. Flashix assumes a modern Python runtime for the backend and a current Node runtime for the frontend and scripts.

## Repository Layout

- `agent/` contains the consolidated FastAPI backend, execution engine, risk logic, settlement helpers, and pipeline tracing services.
- `frontend/` contains the React application with the dashboard, opportunities queue, execution view, risk center, settlement view, market data screen, and compute proof page.
- `compute/` contains TEE-related inference, signature, and validation helpers.
- `contracts/` contains the Hardhat workspace and deployment artifacts for the 0G contracts.
- `scripts/` contains bootstrap, health-check, test, and deployment helpers.
- `docs/` contains the operational and architectural documentation.
- `mempool-listener/` contains the live or simulated opportunity ingestion pipeline.

## Core Environment Areas

Flashix commonly needs four classes of configuration:

1. Backend and agent runtime settings.
2. Compute and TEE credentials.
3. Market data and mempool provider settings.
4. Contract deployment and verification keys.

Typical variables include:

- `GEMINI_API_KEY`
- `TEE_MODE`
- `TEE_ENDPOINT`
- `TEE_API_KEY`
- `TEE_ATTESTATION_CERT_PATH`
- `MEMPOOL_MODE`
- `MEMPOOL_PROVIDER`
- `MEMPOOL_WEBSOCKET_URL`
- `MEMPOOL_API_KEY`
- `RPC_URL`

Use the provider- and environment-specific docs when you need the exact values for each of those groups.

## First-Time Setup

### 1. Clone the Repository

```bash
git clone https://github.com/swanandi-bhende/flashix.git
cd flashix
```

### 2. Create a Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 3. Install Python Dependencies

Install the runtime dependencies first, then the development extras if you plan to run tests or local tooling.

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Install Contract Dependencies

If you want to compile, test, or deploy the Hardhat contracts, install the contract workspace dependencies as well.

```bash
cd contracts
npm install
cd ..
```

### 6. Create Environment Files

Flashix expects local configuration via `.env`-style files. Keep secrets out of version control.

Recommended files:

- Root `.env` for backend and agent runtime settings.
- `frontend/.env` for frontend API base URLs if needed.
- `contracts/.env` for Hardhat deployment credentials and explorer keys.

Useful values include:

- `PERSISTENCE_URL`
- `RPC_URL`
- `TEE_SIGNER_ADDRESS`
- `DEPLOYER_PRIVATE_KEY`
- `BLOCK_EXPLORER_API_KEY`

If you are using live 0G Compute access, also store:

- `TEE_ENDPOINT`
- `TEE_API_KEY`
- `TEE_ATTESTATION_CERT_PATH`
- `TEE_MODE`

If you are using the mempool pipeline, also store:

- `MEMPOOL_MODE`
- `MEMPOOL_PROVIDER`
- `MEMPOOL_WEBSOCKET_URL`
- `MEMPOOL_API_KEY`
- `MEMPOOL_SUBSCRIPTION_TOPICS`

The exact values depend on whether you are running locally, deploying to a testnet, or connecting to the public demo.

## Run the Local Demo Stack

Start the support services in separate terminals.

### Terminal 1: Demo persistence service

```bash
python3 scripts/tee_service.py
```

This service persists demo artifacts such as overrides, exports, and replay evidence.

### Terminal 2: Backend / agent

```bash
source .venv/bin/activate
python -m agent.backend_app
```

The backend exposes the consolidated API that powers the UI pages and demo actions.

### Terminal 3: Frontend

```bash
npm --prefix frontend run dev
```

Vite prints the local URL after startup. In most environments this is `http://localhost:5173`.

### Optional: Mempool listener / live pipeline

```bash
npm run mempool:listen
```

Use this when you want to drive the live opportunity pipeline rather than only the seeded demo flow.

### Optional: Live compute access

If you are using the remote 0G Compute provider instead of the local simulation path, confirm the provider secret and attestation cert are present before starting the agent. The compute docs contain the provisioning flow and security notes.

## Recommended Validation Steps

Run these checks after installation:

```bash
./scripts/health_check.sh
./scripts/run_tests.sh
```

If you are validating the compute or agent reasoning path, also review the replay and signature verification docs before changing signal logic.

For contract verification:

```bash
cd contracts
npx hardhat compile
npx hardhat test
```

## Common Environment Notes

- Use the deployed demo at [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/) if you only need the walkthrough and proof artifacts.
- Use the local app when you need to inspect logs, adjust environment variables, or validate changes in source.
- Keep private keys and API secrets local. Do not commit them.

## Troubleshooting

### Frontend starts but data is empty

Check that the backend is running and that the frontend is pointed at the correct API base URL.

### Demo export links do not appear

Ensure `scripts/tee_service.py` is running before you generate exports from Settlement.

### Contract commands fail

Verify that Node dependencies are installed in `contracts/` and that your Hardhat network configuration matches the target chain.

### Python imports fail

Confirm that your virtual environment is active and that you installed both `requirements.txt` and `requirements-dev.txt`.

### Compute requests fail in live mode

Confirm `TEE_MODE=0g-compute`, the endpoint is reachable, and the attestation certificate path is valid.

### Mempool listener stays disconnected

Confirm the provider credentials, WebSocket URL, and subscription topics are correct, then restart the listener.

## Suggested Next Step

Once the environment is working, open [Demo.md](Demo.md) and follow the guided walkthrough page by page.
