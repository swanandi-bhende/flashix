# TEE Key Rotation Guide

## Overview

This guide provides step-by-step instructions for rotating the TEE signing key, including rollback procedures in case the new key fails verification.

**When to rotate:**
- Current key is suspected compromised
- Enclave code is upgraded (new MRENCLAVE)
- Security policy requires periodic rotation
- Performance testing needs a fresh key

---

## Automated Rotation (Recommended)

The automated rotation script handles all steps safely:

```bash
./scripts/rotate_tee_key.sh
```

The script will:
1. Stop the agent gracefully
2. Generate a new secp256k1 key inside the TEE
3. Register the new key on-chain via `SignalValidator.registerTEE()`
4. Revoke the old key on-chain via `SignalValidator.revokeTEE()`
5. Restart the agent with the new key
6. Wait for the first post-rotation signal to verify

**Output example:**
```
============================================================================
TEE KEY ROTATION
============================================================================

[INFO] Validating environment...
[INFO] Current TEE Address: 0x1234...
[INFO] Current MRENCLAVE: 0xabcd...

============================================================================
Step 1: Stopping Agent
============================================================================

[INFO] Stopping agent (PID: 12345)...
[INFO] Agent stopped

============================================================================
Step 2: Generating New TEE Key Pair
============================================================================

[INFO] Generating new key pair...
New TEE Address: 0x5678...
New Public Key: 0x04...
MRENCLAVE: 0xabcd...

============================================================================
Step 3: Registering New Key On-Chain
============================================================================

[INFO] Registering new TEE on-chain...
Transaction submitted: 0xdef0...
Transaction confirmed in block 12345
Explorer Link: https://testnet.explorer.0g.ai/tx/0xdef0...

============================================================================
KEY ROTATION COMPLETE
============================================================================

[INFO] Summary:
[INFO]   Old TEE Address: 0x1234...
[INFO]   New TEE Address: 0x5678...
[INFO]   Status: ✓ SUCCESS (signals verified)
```

---

## Manual Rotation (Step-by-Step)

If you need more control, follow these steps manually:

### 1. Stop the Agent

```bash
# Find agent PID
ps aux | grep agent

# Kill the process
kill <PID>

# Or use the helper
kill $(cat agent.pid)
```

**Expected:** Agent process exits cleanly. Check logs:
```bash
tail -20 logs/agent.log
```

### 2. Generate New Key Pair

Delete the old keystore and reinitialize:

```bash
# Backup old keystore (optional but recommended)
cp compute/data/keystore.json compute/data/keystore.json.backup

# Delete old keystore
rm compute/data/keystore.json

# Generate new key (run once in TEE enclave)
python3 -c "
from compute.enclave_keystore import EnclaveKeystore
keystore = EnclaveKeystore()
keystore.initialize('compute/data/keystore.json')
print(f'New address: {keystore.get_eth_address()}')
"
```

**Expected output:**
```
New address: 0x5678...
```

Read the new key details:

```bash
python3 -c "
import json
with open('compute/data/keystore.json', 'r') as f:
    data = json.load(f)
print(f'Address: {data[\"eth_address\"]}')
print(f'MRENCLAVE: {data[\"enclave_measurement\"]}')
"
```

### 3. Register New Key On-Chain

```bash
# Set environment variables
export TEE_ETH_ADDRESS=<new_address>
export TEE_MRENCLAVE=<new_mrenclave>
export TEE_ATTESTATION_TYPE=SIMULATION

# Run registration script
cd contracts
npx hardhat run scripts/register_tee.ts --network testnet
```

**Expected output:**
```
SignalValidator Address: 0x...
Transaction submitted: 0xabc...
Transaction confirmed in block 12345
Explorer Link: https://testnet.explorer.0g.ai/tx/0xabc...

Deployments updated: ./deployments/testnet.json
```

Verify on-chain:

```bash
npx hardhat run scripts/verify_tee.ts --network testnet
```

### 4. Revoke Old Key (Optional But Recommended)

```bash
# Create a temporary revocation script
cat > scripts/revoke_temp.ts << 'EOF'
import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function revoke() {
  const oldAddress = "0x1234..."; // Old TEE address
  const [deployer] = await ethers.getSigners();
  
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../deployments/testnet.json"), "utf8")
  );
  const sv = await ethers.getContractAt("SignalValidator", deployments.SignalValidator);
  
  const tx = await sv.revokeTEE(oldAddress);
  const receipt = await tx.wait(1);
  console.log(`Revoked ${oldAddress} at block ${receipt?.blockNumber}`);
}

revoke().catch(console.error);
EOF

npx hardhat run scripts/revoke_temp.ts --network testnet
rm scripts/revoke_temp.ts
```

Verify revocation:

```bash
npx hardhat run -c "
const sv = await ethers.getContractAt('SignalValidator', '<address>');
console.log(await sv.isTEEActive('0x1234...'));  // Should print false
"
```

### 5. Restart Agent

```bash
./scripts/start_agent.sh
```

Monitor startup:

```bash
tail -f logs/agent.log
```

**Expected output:**
```
[AGENT] Keystore initialized
[AGENT] Connecting to on-chain verifier
[AGENT] Listening for opportunities...
```

### 6. Verify First Signal

Wait for an arbitrage opportunity and monitor the first signal verification:

```bash
# Monitor in real-time
tail -f logs/agent.log | grep -E "VERIFIED|ERROR|FAILED"
```

**Success case:**
```
[VERIFIED] Signal 0xabc... verified on-chain
[VERIFIED] Trade executed: borrowAmount=100000, expectedProfit=500
```

**Failure case:**
```
[ERROR] Signal verification failed: MRENCLAVE mismatch
[CRITICAL] This should not happen if rotation was successful
```

---

## Rollback (If Rotation Fails)

If post-rotation signals fail verification, rollback to the old key:

### 1. Stop Current Agent

```bash
kill $(cat agent.pid)
```

### 2. Restore Old Keystore

```bash
# If you backed up earlier
cp compute/data/keystore.json.backup compute/data/keystore.json
```

OR regenerate from secure storage:
```bash
# Contact DevOps for backup of old keystore
scp devops@backup.server:/secure/keystore.json.backup ./
cp ./keystore.json.backup ./compute/data/keystore.json
```

### 3. Re-register Old Key

```bash
# Read old key details from backup
python3 -c "
import json
with open('compute/data/keystore.json', 'r') as f:
    data = json.load(f)
print(f'export TEE_ETH_ADDRESS={data[\"eth_address\"]}')
print(f'export TEE_MRENCLAVE={data[\"enclave_measurement\"]}')
" > /tmp/old_key_vars.sh

source /tmp/old_key_vars.sh

# Re-register
cd contracts
npx hardhat run scripts/register_tee.ts --network testnet
```

### 4. Revoke Failed Key (New Key)

```bash
cat > scripts/revoke_failed.ts << 'EOF'
import { ethers } from "hardhat";
import * as fs from "fs";

async function revoke() {
  const failedAddress = "0x5678..."; // New key that failed
  const [deployer] = await ethers.getSigners();
  
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../deployments/testnet.json"), "utf8")
  );
  const sv = await ethers.getContractAt("SignalValidator", deployments.SignalValidator);
  
  const tx = await sv.revokeTEE(failedAddress);
  const receipt = await tx.wait(1);
  console.log(`Revoked ${failedAddress}`);
}

revoke().catch(console.error);
EOF

npx hardhat run scripts/revoke_failed.ts --network testnet
rm scripts/revoke_failed.ts
```

### 5. Restart Agent with Old Key

```bash
./scripts/start_agent.sh
```

Monitor:

```bash
tail -f logs/agent.log | grep -E "VERIFIED|ERROR"
```

If signals verify successfully, the old key is restored and the rotation can be retried later.

---

## Troubleshooting

### "MRENCLAVE mismatch" after rotation

**Cause:** The new key was registered with the wrong MRENCLAVE, or the smart contract's `EXPECTED_MRENCLAVE` wasn't updated.

**Solution:**
```bash
# Check the registered MRENCLAVE
npx hardhat run -c "
const sv = await ethers.getContractAt('SignalValidator', '<address>');
const reg = await sv.teeRegistrations('<new_address>');
console.log('Registered MRENCLAVE:', reg.mrenclave);
"

# Check the expected value
npx hardhat run -c "
const sv = await ethers.getContractAt('SignalValidator', '<address>');
console.log('EXPECTED_MRENCLAVE:', await sv.EXPECTED_MRENCLAVE());
"

# If they don't match, owner must call:
npx hardhat run -c "
const sv = await ethers.getContractAt('SignalValidator', '<address>');
const newMrenclave = '0x...'; // From the new keystore
const tx = await sv.setExpectedMrenclave(newMrenclave);
await tx.wait(1);
console.log('Updated EXPECTED_MRENCLAVE');
"
```

### "Signal already used" after rotation

**Cause:** An opportunity ID was processed with the old key and is being re-attempted with the new key.

**Solution:** This is a safety feature to prevent replays. If the opportunity is still valid:
1. Wait for a new arbitrage opportunity
2. Do not retry the same opportunity ID

If you must retry a specific opportunity, the contract owner must reset the nonce:
```bash
# Contact owner to add a nonce reset function (not currently implemented)
```

### Agent won't start after rotation

**Cause:** Keystore corruption or agent configuration issue.

**Steps:**
```bash
# Check keystore integrity
python3 -c "
from compute.enclave_keystore import EnclaveKeystore
keystore = EnclaveKeystore()
try:
    keystore.initialize('compute/data/keystore.json')
    print(f'✓ Keystore OK: {keystore.get_eth_address()}')
except Exception as e:
    print(f'✗ Keystore error: {e}')
"

# Check environment variables
echo "TEE_ETH_ADDRESS: $TEE_ETH_ADDRESS"
echo "TEE_MRENCLAVE: $TEE_MRENCLAVE"

# Check logs
tail -50 logs/agent.log | grep ERROR

# If keystore is corrupted, rollback to backup
cp compute/data/keystore.json.backup compute/data/keystore.json
```

---

## Security Considerations

1. **Backup Before Rotation:** Always backup the old keystore before generating a new one.
2. **Air-Gapped Backup:** Store the old keystore backup on an air-gapped machine or encrypted external drive.
3. **Revocation Confirmation:** Always verify that the old key was revoked on-chain before considering rotation complete.
4. **Monitor Signals:** Watch for at least one successful signal verification post-rotation before considering the new key trusted.
5. **Slow Rollout:** If rotating during a live hackathon, do it during a low-activity period and have rollback plan ready.

---

## Automation (CI/CD)

For automated key rotation based on schedule or policy, integrate into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
name: Rotate TEE Key

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup environment
        run: |
          echo "NETWORK=testnet" >> $GITHUB_ENV
          echo "TEE_KEYSTORE_PASSPHRASE=${{ secrets.TEE_KEYSTORE_PASSPHRASE }}" >> $GITHUB_ENV
      
      - name: Rotate key
        run: ./scripts/rotate_tee_key.sh --no-confirm
      
      - name: Notify
        run: |
          # Send slack notification with new address
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -d "TEE key rotated. New address: ..."
```

---

## References

- [Cryptographic Trust Chain Architecture](/compute/README.md#cryptographic-trust-chain-architecture)
- [Key Generation & Storage](/compute/README.md#key-generation--storage)
- [SignalValidator.sol](../contracts/SignalValidator.sol)
- [register_tee.ts](../contracts/scripts/register_tee.ts)
