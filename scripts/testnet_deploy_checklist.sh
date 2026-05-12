#!/usr/bin/env bash
set -euo pipefail

ZG_TESTNET_RPC="${ZG_TESTNET_RPC:-}"

echo "Running pre-deployment checklist..."

fail() {
  echo "CHECK_FAILED: $1" >&2
  FAILED=true
}

FAILED=false

echo "1) Compile contracts (cd contracts && npx hardhat compile --force)"
cd contracts && npx hardhat compile --force || fail "hardhat compile failed"

echo "2) Run local test suite (cd contracts && npx hardhat test --network hardhat)"
cd contracts && npx hardhat test --network hardhat || fail "hardhat tests failed"

echo "3) Run integration tests (python tests/run_integration_tests.py --data-source SYNTHETIC --n-opportunities 30)"
if ! python3 tests/run_integration_tests.py --data-source SYNTHETIC --n-opportunities 30 | tee /tmp/integration.out; then
  fail "integration tests failed"
else
  if ! grep -q "mainnet_release_ready=True" /tmp/integration.out; then
    fail "integration tests did not report mainnet_release_ready=True"
  fi
fi

echo "4) Run replay harness (python tests/replay/replay_harness.py --ci-mode)"
if ! python3 tests/replay/replay_harness.py --ci-mode | tee /tmp/replay.out; then
  fail "replay harness failed"
else
  if ! grep -q "release_recommended=True" /tmp/replay.out; then
    fail "replay harness did not recommend release readiness"
  fi
fi

echo "5) Check 0G testnet RPC reachability"
if [ -z "$ZG_TESTNET_RPC" ]; then
  fail "ZG_TESTNET_RPC not set in environment"
else
  BLOCK_NUM=$(curl -s -X POST "$ZG_TESTNET_RPC" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}' | jq -r '.result' || true)
  if [ -z "$BLOCK_NUM" ] || [ "$BLOCK_NUM" = "null" ]; then
    fail "0G testnet RPC did not return a valid block number"
  fi
fi

echo "6) Check deployer wallet balance (python scripts/check_wallet_balance.py --min-eth 0.5)"
if ! python3 scripts/check_wallet_balance.py --min-eth 0.5; then
  fail "deployer wallet balance check failed"
fi

echo "7) Verify required .env variables"
REQUIRED=(ZG_TESTNET_RPC DEPLOYER_PRIVATE_KEY GEMINI_API_KEY TEE_ENDPOINT MEMPOOL_API_KEY)
for v in "${REQUIRED[@]}"; do
  if [ -z "${!v:-}" ]; then
    fail "Environment variable $v is not set or empty"
  fi
done

if [ "$FAILED" = false ]; then
  echo "ALL PRE-DEPLOYMENT CHECKS PASSED — safe to deploy"
  exit 0
else
  echo "One or more pre-deployment checks failed. See above messages."
  exit 1
fi
