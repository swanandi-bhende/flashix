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

Contributing
------------
See CONTRIBUTING.md for development guidelines, code style, testing, and PR workflow.

Hackathon Resources
-------------------
- 0G docs: https://0g.ai/docs
- HackQuest portal: https://hackquest.example.com
# flashix
Submission for 0G APAC Hackathon 2026.
