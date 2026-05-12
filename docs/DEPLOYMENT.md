# Deployment

This document is the runbook for deploying Flashix smart contracts to 0G Chain.

## Networks

- 0G Testnet (Galileo)
  - RPC: https://evmrpc-testnet.0g.ai
	- Chain ID: 16602
  - Explorer: https://chainscan-galileo.0g.ai/
  - Faucet: https://faucet-testnet.0g.ai/
- 0G Mainnet
  - RPC: https://evmrpc.0g.ai
  - Chain ID: 16600

## Prerequisites

1. Install dependencies in contracts workspace:
	- cd contracts
	- npm install
2. Create environment file:
	- cp .env.example .env
3. Set environment variables:
	- DEPLOYER_PRIVATE_KEY (64 hex chars, with or without 0x prefix)
	- TEE_SIGNER_ADDRESS
	- BLOCK_EXPLORER_API_KEY (for source verification)
4. Fund deployer wallet with at least 0.1 testnet ETH equivalent.

## Compile And Test

1. Compile:
	- npx hardhat compile
2. Run tests:
	- npx hardhat test
3. Run coverage:
	- npx hardhat coverage

## Deploy To 0G Testnet

Run complete deployment:

- npx hardhat run scripts/deploy_all.ts --network zgTestnet

This deploys in order:

1. SignalValidator
2. LendingPool
3. ArbitrageExecutor
4. Wiring calls:
	- setSignalValidator(...)
	- setLendingPool(...)

## Post-Deployment Validation

Run health checks:

- npx hardhat run scripts/verify_deployment.ts --network zgTestnet

Expected checks:

1. LendingPool responds to FEE_BPS()
2. SignalValidator responds to getTrustedSigner()
3. ArbitrageExecutor responds to getExecutionCount()

## Explorer Source Verification

Use Hardhat verify after deployment addresses are known:

- npx hardhat verify --network zgTestnet <SIGNAL_VALIDATOR_ADDRESS> <TEE_SIGNER_ADDRESS>
- npx hardhat verify --network zgTestnet <LENDING_POOL_ADDRESS>
- npx hardhat verify --network zgTestnet <ARBITRAGE_EXECUTOR_ADDRESS> <PROFIT_RECIPIENT_ADDRESS>

After verification, confirm each contract page has:

1. Verified badge
2. Source visible in Contract tab
3. Read Contract functions callable

## Required Deployment Artifacts

Persist these files after every deployment:

1. contracts/deployments/testnet.json
2. contracts/abi/LendingPool.json
3. contracts/abi/SignalValidator.json
4. contracts/abi/ArbitrageExecutor.json

Also record:

1. Deployment tx hashes
2. Contract addresses
3. Block numbers
4. Gas used
5. Explorer URLs

## Manual Submission Checklist

1. Update README "Deployed Contracts (Testnet)" links.
2. Capture and store explorer screenshots for all 3 contracts.
3. Commit deployments/testnet.json with final addresses and verification links.
4. Confirm frontend and agent read addresses from contracts/abi files.

## Testnet Pre-deployment Checklist Script

Before any 0G testnet deployment, run the included pre-deployment checklist and ensure it exits cleanly:

- `scripts/testnet_deploy_checklist.sh` — this script compiles contracts, runs unit and integration tests, executes the replay harness checks, verifies RPC reachability, validates deployer balance, and ensures required environment variables are set.

Make the script executable and run it interactively:

```bash
chmod +x scripts/testnet_deploy_checklist.sh
./scripts/testnet_deploy_checklist.sh
```

If the script reports any failures, resolve them before attempting to deploy to 0G testnet.
