Autonomous TEE-sealed AI agent that detects and executes flashloan-funded perpetual arbitrage across global DEXs using sealed inference on private mempool + liquidity snapshots.

Problem Statement
-----------------
Perpetual swap arbitrage is frequently profitable but vulnerable to front-running, MEV extraction, and leakage of sensitive mempool and liquidity data. Traders and researchers need an architecture that ensures deterministic, private inference over sensitive market snapshots while enabling atomic execution for low-latency arbitrage.

Core Innovation
---------------
- 0G Chain for atomic flashloan execution and deterministic on-chain settlement.
- 0G Compute for deterministic sealed inference (TEE) preventing data leakage of private mempool and liquidity snapshots.
- LangChain + Gemini as an autonomous reasoning layer that proposes, validates, and sequences arbitrage actions.

System Architecture (high-level)
--------------------------------
Flow: mempool listener → arbitrage detector → 0G Compute (sealed inference) → LangChain agent → on-chain execution (0G Chain) → settlement

Quick Start
-----------
- Clone the repo: `git clone https://github.com/swanandi-bhende/flashix.git && cd flashix`
- Run the bootstrap script: `./setup.sh`
- Copy `.env.example` → `.env.local` and fill secrets
- Start mempool listener: `npm run mempool:listen`
- Start agent: `./scripts/start_agent.sh` (or `python -m agent.flashloan_agent`)
- Run unit tests: `./scripts/run_tests.sh`

Smart Contract Flow (0G Chain)
------------------------------
- Hardhat project: `contracts/`
- Compile: `cd contracts && npx hardhat compile`
- Test: `npx hardhat test`
- Coverage: `npx hardhat coverage`
- Deploy to 0G testnet: `npx hardhat run scripts/deploy_all.ts --network zgTestnet`
- Verify deployment health: `npx hardhat run scripts/verify_deployment.ts --network zgTestnet`
- Verify source code: `npx hardhat verify --network zgTestnet ...`

Deployed Contracts (Testnet)
----------------------------
**0G Chain Galileo Testnet (Chain ID: 16602)**

- **LendingPool**: `0x69d998618c7AEA1224C4bc5898519613c86EE42d`
  - Deployed: Block 32478557, Tx `0xea8f388e407fd799491038852f9b2751e638a89c67e8db5dc05136c8cde5f683`
  - Explorer: https://chainscan-galileo.0g.ai/address/0x69d998618c7AEA1224C4bc5898519613c86EE42d
  - Gas used: 996,161

- **SignalValidator**: `0xe6329A48C0D8E4152e8406dbe102078E1abC7484`
  - Deployed: Block 32478529, Tx `0xb88a89c1ef143df9edb63a159fb306a7a5b3c7b8da84462fdc4d82ca6a3340a6`
  - Explorer: https://chainscan-galileo.0g.ai/address/0xe6329A48C0D8E4152e8406dbe102078E1abC7484
  - Gas used: 720,357

- **ArbitrageExecutor**: `0xAa0e986143B144f5860C41c74552B67ca78b1EBB`
  - Deployed: Block 32478586, Tx `0x61e20e49289ddfcba96e897b13d43214e0580c53b94a0be15fb800ffb59e1964`
  - Explorer: https://chainscan-galileo.0g.ai/address/0xAa0e986143B144f5860C41c74552B67ca78b1EBB
  - Gas used: 1,203,516

**Verification Status:**
- All contracts deployed successfully and callable on 0G Chain testnet
- Source code submission on ChainScan currently returns a compiler error for the fresh deployment
- Health check passed (all state variables verified)

Contributing
------------
See CONTRIBUTING.md for development guidelines, code style, testing, and PR workflow.

Hackathon Resources
-------------------
- 0G docs: https://0g.ai/docs
- HackQuest portal: https://hackquest.example.com
# flashix
Submission for 0G APAC Hackathon 2026.
