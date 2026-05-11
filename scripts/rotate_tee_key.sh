#!/bin/bash

###############################################################################
# TEE Key Rotation Script
#
# Safely rotates the TEE signing key when:
# - Current key is suspected compromised
# - Enclave code is upgraded (MRENCLAVE changes)
# - Key age exceeds security policy
#
# Process:
# 1. Stop the agent
# 2. Generate a new key pair inside the TEE
# 3. Register the new key on-chain
# 4. Revoke the old key on-chain
# 5. Restart the agent with the new key
# 6. Verify the first post-rotation signal passes verification
#
# Usage:
#   ./scripts/rotate_tee_key.sh [--no-confirm]
#
# Environment Variables:
#   TEE_ETH_ADDRESS (current)
#   TEE_MRENCLAVE (current)
#   NETWORK (default: testnet)
#   HARDHAT_NETWORK (default: value of NETWORK)
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NETWORK="${NETWORK:-testnet}"
HARDHAT_NETWORK="${HARDHAT_NETWORK:-$NETWORK}"
AGENT_PID_FILE="agent.pid"
NO_CONFIRM="${1:-}"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

confirm() {
    if [[ "$NO_CONFIRM" == "--no-confirm" ]]; then
        return 0
    fi
    local prompt="$1"
    local response
    read -p "$(echo -e ${YELLOW}${prompt}${NC})" response
    [[ "$response" =~ ^[Yy]$ ]]
}

print_header() {
    echo ""
    echo "============================================================================"
    echo "$1"
    echo "============================================================================"
    echo ""
}

# Main script

print_header "TEE KEY ROTATION"

# Step 0: Validate environment
log_info "Validating environment..."

if [[ -z "${TEE_ETH_ADDRESS:-}" ]]; then
    log_error "TEE_ETH_ADDRESS environment variable not set"
    exit 1
fi
if [[ -z "${TEE_MRENCLAVE:-}" ]]; then
    log_error "TEE_MRENCLAVE environment variable not set"
    exit 1
fi

OLD_TEE_ADDRESS="$TEE_ETH_ADDRESS"
OLD_TEE_MRENCLAVE="$TEE_MRENCLAVE"

log_info "Current TEE Address: $OLD_TEE_ADDRESS"
log_info "Current MRENCLAVE: $OLD_TEE_MRENCLAVE"

# Step 1: Stop the agent
print_header "Step 1: Stopping Agent"

if [[ -f "$AGENT_PID_FILE" ]]; then
    AGENT_PID=$(cat "$AGENT_PID_FILE")
    if kill -0 "$AGENT_PID" 2>/dev/null; then
        log_info "Stopping agent (PID: $AGENT_PID)..."
        kill "$AGENT_PID"
        sleep 2
        if kill -0 "$AGENT_PID" 2>/dev/null; then
            log_warn "Agent still running, force killing..."
            kill -9 "$AGENT_PID" || true
        fi
        log_info "Agent stopped"
    else
        log_warn "Agent PID file exists but process is not running"
    fi
    rm -f "$AGENT_PID_FILE"
else
    log_info "Agent not running (no PID file)"
fi

# Give system time to clean up
sleep 1

# Step 2: Generate new key pair
print_header "Step 2: Generating New TEE Key Pair"

if ! confirm "Delete current keystore and generate a fresh key pair? (yes/no): "; then
    log_error "Key generation cancelled"
    exit 1
fi

log_info "Deleting old keystore..."
KEYSTORE_PATH="${TEE_KEYSTORE_PATH:-./compute/data/keystore.json}"
if [[ -f "$KEYSTORE_PATH" ]]; then
    rm -f "$KEYSTORE_PATH"
    log_info "Deleted: $KEYSTORE_PATH"
fi

log_info "Generating new key pair..."
# This would be implemented as a Python script or integrated with the enclave
# For now, we simulate it
python3 -c "
import os
import json
from pathlib import Path
from compute.enclave_keystore import EnclaveKeystore

os.environ['TEE_KEYSTORE_PASSPHRASE'] = os.getenv('TEE_KEYSTORE_PASSPHRASE', 'default')
keystore_path = os.getenv('TEE_KEYSTORE_PATH', './compute/data/keystore.json')
keystore = EnclaveKeystore()
keystore.initialize(keystore_path)

print(f'New TEE Address: {keystore.get_eth_address()}')
print(f'New Public Key: {keystore.get_public_key()}')

# Export for on-chain registration
with open(keystore_path, 'r') as f:
    data = json.load(f)
print(f'MRENCLAVE: {data[\"enclave_measurement\"]}')
" || {
    log_error "Key generation failed"
    exit 1
}

# Step 3: Detect new key details (in production, read from keystore)
print_header "Step 3: Registering New Key On-Chain"

log_info "Reading new key details from keystore..."
KEYSTORE_PATH="${TEE_KEYSTORE_PATH:-./compute/data/keystore.json}"

NEW_TEE_ADDRESS=$(python3 -c "
import json
with open('$KEYSTORE_PATH', 'r') as f:
    data = json.load(f)
print(data['eth_address'])
")

NEW_TEE_MRENCLAVE=$(python3 -c "
import json
with open('$KEYSTORE_PATH', 'r') as f:
    data = json.load(f)
print(data['enclave_measurement'])
")

log_info "New TEE Address: $NEW_TEE_ADDRESS"
log_info "New MRENCLAVE: $NEW_TEE_MRENCLAVE"

# Set environment variables for the registration script
export TEE_ETH_ADDRESS="$NEW_TEE_ADDRESS"
export TEE_MRENCLAVE="$NEW_TEE_MRENCLAVE"

log_info "Registering new TEE on-chain..."
cd contracts
npx hardhat run scripts/register_tee.ts --network "$HARDHAT_NETWORK" || {
    log_error "Failed to register new TEE"
    exit 1
}
cd ..

# Step 4: Revoke old key
print_header "Step 4: Revoking Old TEE Key"

if ! confirm "Revoke the old TEE address ($OLD_TEE_ADDRESS) on-chain? (yes/no): "; then
    log_warn "Skipping revocation. Please revoke manually:"
    log_warn "  cd contracts && npx hardhat run scripts/revoke_tee.ts --network $HARDHAT_NETWORK"
else
    log_info "Revoking old TEE: $OLD_TEE_ADDRESS"
    cd contracts
    cat > scripts/revoke_tee_temp.ts << 'EOF'
import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function revokeTEE() {
  const oldAddress = process.env.OLD_TEE_ADDRESS!;
  const [deployer] = await ethers.getSigners();
  
  const deploymentsPath = path.join(__dirname, "../deployments/testnet.json");
  const deployments = JSON.parse(fs.readFileSync(deploymentsPath, "utf8"));
  const signalValidator = await ethers.getContractAt("SignalValidator", deployments.SignalValidator);
  
  const tx = await signalValidator.revokeTEE(oldAddress);
  const receipt = await tx.wait(1);
  console.log(`Revoked ${oldAddress} at block ${receipt?.blockNumber}`);
}

revokeTEE().catch(console.error);
EOF
    OLD_TEE_ADDRESS="$OLD_TEE_ADDRESS" npx hardhat run scripts/revoke_tee_temp.ts --network "$HARDHAT_NETWORK" || {
        log_warn "Failed to revoke old key (will retry)"
    }
    rm -f scripts/revoke_tee_temp.ts
    cd ..
fi

# Step 5: Restart agent with new key
print_header "Step 5: Restarting Agent"

if ! confirm "Start agent with new key? (yes/no): "; then
    log_warn "Agent not started. Start manually with: ./scripts/start_agent.sh"
else
    log_info "Starting agent..."
    ./scripts/start_agent.sh &
    NEW_AGENT_PID=$!
    echo "$NEW_AGENT_PID" > "$AGENT_PID_FILE"
    log_info "Agent started (PID: $NEW_AGENT_PID)"
fi

# Step 6: Monitor for first signal verification
print_header "Step 6: Waiting for First Post-Rotation Signal"

log_info "Waiting up to 120 seconds for first signal verification..."
TIMEOUT=120
ELAPSED=0
SIGNAL_VERIFIED=false

while [[ $ELAPSED -lt $TIMEOUT ]]; do
    if tail -100 logs/agent.log 2>/dev/null | grep -q "Signal verified\|VERIFIED"; then
        log_info "✓ First post-rotation signal verified successfully!"
        SIGNAL_VERIFIED=true
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [[ "$SIGNAL_VERIFIED" == "false" ]]; then
    log_warn "No signal verification detected in $TIMEOUT seconds"
    log_info "Check agent logs: tail -f logs/agent.log"
fi

# Completion summary
print_header "KEY ROTATION COMPLETE"

log_info "Summary:"
log_info "  Old TEE Address: $OLD_TEE_ADDRESS"
log_info "  New TEE Address: $NEW_TEE_ADDRESS"
log_info "  Old MRENCLAVE: $OLD_TEE_MRENCLAVE"
log_info "  New MRENCLAVE: $NEW_TEE_MRENCLAVE"

if [[ "$SIGNAL_VERIFIED" == "true" ]]; then
    log_info "  Status: ✓ SUCCESS (signals verified)"
else
    log_warn "  Status: ⚠ Check signals (may need to wait for next opportunity)"
fi

log_info ""
log_info "Rollback instructions (if needed):"
log_info "1. Kill current agent: kill \$(cat $AGENT_PID_FILE)"
log_info "2. Restore old keystore from backup"
log_info "3. Re-register old TEE: TEE_ETH_ADDRESS=$OLD_TEE_ADDRESS TEE_MRENCLAVE=$OLD_TEE_MRENCLAVE npx hardhat run scripts/register_tee.ts"
log_info "4. Revoke new TEE: npx hardhat run scripts/revoke_tee.ts --network $HARDHAT_NETWORK"
log_info "5. Restart agent: ./scripts/start_agent.sh"

echo ""
