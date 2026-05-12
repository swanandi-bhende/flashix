#!/usr/bin/env bash
set -euo pipefail

NETWORK=zgTestnet
LOGFILE=deploy_testnet.log
mkdir -p deployments

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

echo "DEPLOYMENT_START: $(timestamp), chain=0G_TESTNET, deployer=$(python3 scripts/get_deployer_address.py)" | tee -a "$LOGFILE"

trap 'echo "DEPLOYMENT_FAILED at unknown step" | tee -a "$LOGFILE"; echo "Run scripts/cleanup_failed_deployment.sh" >&2; exit 1' ERR

run_step() {
  local step_desc="$1"; shift
  echo "START_STEP: $step_desc" | tee -a "$LOGFILE"
  if ! "$@" 2>&1 | tee -a "$LOGFILE"; then
    echo "DEPLOYMENT_FAILED at step: $step_desc" | tee -a "$LOGFILE"
    echo "Run scripts/cleanup_failed_deployment.sh before retrying" | tee -a "$LOGFILE"
    exit 1
  fi
  echo "COMPLETE_STEP: $step_desc" | tee -a "$LOGFILE"
}

run_step "deploy SignalValidator" npx hardhat run contracts/scripts/deploy_signal_validator.ts --network $NETWORK
SV_ADDR=$(grep -oE "SignalValidator deployed at: 0x[0-9a-fA-F]{40}" "$LOGFILE" | tail -n1 | awk '{print $4}')

run_step "deploy LendingPool" npx hardhat run contracts/scripts/deploy_lending_pool.ts --network $NETWORK
LP_ADDR=$(grep -oE "LendingPool deployed at: 0x[0-9a-fA-F]{40}" "$LOGFILE" | tail -n1 | awk '{print $4}')

run_step "deploy ArbitrageExecutorV2" npx hardhat run contracts/scripts/deploy_arbitrage_executor_v2.ts --network $NETWORK --signalValidator "$SV_ADDR" --lendingPool "$LP_ADDR"
AE_ADDR=$(grep -oE "ArbitrageExecutorV2 deployed at: 0x[0-9a-fA-F]{40}" "$LOGFILE" | tail -n1 | awk '{print $4}')

run_step "register TEE" npx hardhat run contracts/scripts/register_tee.ts --network $NETWORK
TEE_ADDR=$(grep -oE "TEE registered at: 0x[0-9a-fA-F]{40}" "$LOGFILE" | tail -n1 | awk '{print $4}') || TEE_ADDR=""

run_step "seed LendingPool with 500 USDC" npx hardhat run contracts/scripts/seed_lending_pool.ts --network $NETWORK --amount 500

run_step "verify deployment (view checks)" npx hardhat run contracts/scripts/verify_deployment.ts --network $NETWORK

DEPLOYER=$(python3 scripts/get_deployer_address.py)
cat > deployments/testnet.json <<EOF
{
  "network": "zgTestnet",
  "chainId": 16600,
  "deployedAt": "$(timestamp)",
  "signalValidator": "${SV_ADDR}",
  "lendingPool": "${LP_ADDR}",
  "arbitrageExecutorV2": "${AE_ADDR}",
  "teeAddress": "${TEE_ADDR}",
  "lendingPoolBalance": "500 USDC",
  "deployer": "${DEPLOYER}",
  "txHashes": {}
}
EOF

run_step "source verification" npx hardhat run contracts/scripts/verify_deployment.ts --network $NETWORK

echo "DEPLOYMENT_COMPLETE: all contracts verified on 0G Explorer" | tee -a "$LOGFILE"
echo "deployment file: deployments/testnet.json"
