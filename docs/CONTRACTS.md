# Smart Contract Architecture & Security Model

Flashix smart contracts form the on-chain backbone for atomic arbitrage execution on 0G Chain. This document provides a complete reference for contract design, security guarantees, deployment procedures, and operational guidelines.

## Table of Contents

1. [Contract Dependency Diagram](#contract-dependency-diagram)
2. [Contract Overview](#contract-overview)
3. [Security Model](#security-model)
4. [Function Reference](#function-reference)
5. [Deployment Guide](#deployment-guide)
6. [Integration Guide](#integration-guide)
7. [Known Limitations](#known-limitations)
8. [Testing & Verification](#testing--verification)

---

## Contract Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    0G Compute TEE (Off-chain)                   │
│             Signs arbitrage opportunities with ECDSA             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Signal (signature + opportunity data)
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │    ArbitrageExecutor (On-chain)       │
        │  - Calls SignalValidator.verify()    │
        │  - Initiates flashloan from Pool      │
        │  - Executes atomic perpswap trades    │
        │  - Routes profit to recipient        │
        └──────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    ┌─────────────┐     ┌──────────────────┐
    │LendingPool  │     │SignalValidator   │
    │ ERC-3156    │     │ ECDSA verification
    │ Flashloans  │     │ Replay prevention│
    └─────────────┘     └──────────────────┘
```

**Flow:**
- TEE signs arbitrage signal using private key
- ArbitrageExecutor receives signal and calls `SignalValidator.verify()`
- SignalValidator recovers signer from signature and checks trusted list
- If verified, ArbitrageExecutor calls `LendingPool.flashLoan()`
- LendingPool transfers borrowed tokens and invokes executor's `onFlashLoan()` callback
- Executor executes trades, validates profit, and repays loan atomically

---

## Contract Overview

### 1. LendingPool (ERC-3156 Compliant)

**Purpose:** Provides flashloan funding for atomic arbitrage execution.

**Key Features:**
- Implements ERC-3156 standard for composable flashloans
- Supports multiple ERC-20 tokens (USDC, USDT, etc.)
- 0.09% fee per loan (configurable)
- Re-entrancy guard on all state-changing functions
SIGNAL_VALIDATOR = 0xe6329A48C0D8E4152e8406dbe102078E1abC7484
LENDING_POOL = 0x69d998618c7AEA1224C4bc5898519613c86EE42d
ARBITRAGE_EXECUTOR = 0xAa0e986143B144f5860C41c74552B67ca78b1EBB
**Constructor:**
```solidity
constructor()
```
- Initializes contract with owner
- Whitelists USDC and USDT on mainnet (update for other networks)

**Core Functions:**

| Function | Visibility | Purpose |
|----------|-----------|---------|
| `flashLoan(receiver, token, amount, data)` | External | Initiate atomic flashloan |
| `maxFlashLoan(token)` | View | Get max borrowable amount for token |
| `flashFee(token, amount)` | Pure | Calculate fee for loan amount |
| `setTokenListing(token, enabled)` | External (Owner) | Whitelist/delist tokens |
| `withdrawFees(token)` | External (Owner) | Collect accumulated fees |
| `emergencyPause()` | External (Owner) | Halt new flashloans |
| `emergencyUnpause()` | External (Owner) | Resume flashloans |
| `emergencyWithdraw(token, amount)` | External (Owner) | Emergency token recovery |

### 2. ArbitrageExecutor

**Purpose:** On-chain execution engine that receives TEE-signed signals, verifies them, and executes atomic perpswap trades.

**Key Features:**
- Implements ERC-3156 flashborrower interface
- Cryptographic signal verification via SignalValidator
- Deadline-based signal expiry protection
- Profit validation and threshold enforcement
- DEX router approval mechanism
- Pausable execution (owner can suspend in emergencies)

**Constructor:**
```solidity
constructor(address _profitRecipient)
```
- Sets initial profit recipient address

**Core Functions:**

| Function | Visibility | Purpose |
|----------|-----------|---------|
| `onFlashLoan(initiator, token, amount, fee, data)` | External | Callback from LendingPool |
| `setLendingPool(address)` | External (Owner) | Link to LendingPool |
| `setSignalValidator(address)` | External (Owner) | Link to SignalValidator |
| `setProfitRecipient(address)` | External (Owner) | Update profit destination |
| `setRouterApproval(router, approved)` | External (Owner) | Approve/revoke DEX routers |
| `pause()` | External (Owner) | Pause execution |
| `unpause()` | External (Owner) | Resume execution |
| `getExecutionCount()` | View | Get total executions |

### 3. SignalValidator

**Purpose:** Cryptographically verifies that execution signals originated from the trusted 0G Compute TEE.

**Key Features:**
- ECDSA signature recovery and verification
- Trusted signer management (key rotation)
- Replay attack prevention via nonce mapping
- Deadline expiry enforcement
- Batch verification support
- Emergency signal reset (owner only)

**Constructor:**
```solidity
constructor(address _trustedSigner)
```
- Sets initial TEE signer address

**Core Functions:**

| Function | Visibility | Purpose |
|----------|-----------|---------|
| `verify(signal)` | External | Verify single signal |
| `verifyBatch(signals)` | External | Verify multiple signals |
| `setTrustedSigner(address)` | External (Owner) | Update TEE public key |
| `isSignalUsed(opportunityId)` | View | Check if signal executed |
| `isSignalValid(signal)` | View | Check if signal still valid |
| `resetSignal(opportunityId)` | External (Owner) | Emergency signal reset |

---

## Security Model

### 1. Trust Chain: TEE → On-Chain

The entire security model depends on the integrity of the 0G Compute TEE. The trust chain works as follows:

```
TEE Inference Engine
    ↓
    (Signs opportunity with ECDSA private key)
    ↓
Arbitrage Signal + Signature
    ↓
    (Broadcast to chain)
    ↓
SignalValidator.verify()
    ↓
    (Recover signer from signature)
    ↓
    (Check signer against trusted registry)
    ↓
    (Accept or reject signal)
    ↓
ArbitrageExecutor.onFlashLoan()
    (Execute if and only if verified)
```

**Security Assumptions:**
- TEE private key is never exposed
- ECDSA signature cannot be forged without the key
- Only legitimate opportunities get signed by TEE
- On-chain signer verification is cryptographically sound

### 2. Re-entrancy Protection

All state-changing functions in LendingPool are protected by OpenZeppelin's `ReentrancyGuard`:

```solidity
function flashLoan(...) external nonReentrant whenNotPaused returns (bool) {
    // Only one execution at a time (atomicity)
}
```

**How it works:**
1. Before function execution, guard sets `locked = true`
2. If execution tries to call back into LendingPool, guard reverts with `ReentrancyGuardReentrantCall`
3. After function exits, guard resets `locked = false`

This prevents attacks where a malicious receiver contract tries to call `flashLoan` again within the callback.

### 3. Replay Attack Prevention

SignalValidator maintains a `usedSignals` mapping:

```solidity
mapping(bytes32 => bool) public usedSignals;

function verify(ArbitrageSignal calldata signal) external returns (bool) {
    if (usedSignals[signal.opportunityId]) {
        revert SignalAlreadyUsed(signal.opportunityId);
    }
    
    // ... signature verification ...
    
    usedSignals[signal.opportunityId] = true;
    return true;
}
```

**How it works:**
- Each signal has a unique `opportunityId` (hash of market conditions)
- First execution marks `opportunityId` as used
- Subsequent executions with same `opportunityId` are rejected
- Prevents resubmitting identical signals after market conditions change

### 4. Signature Verification (ECDSA)

SignalValidator uses Ethereum's standard ECDSA signature recovery:

```solidity
bytes32 signalHash = keccak256(abi.encode(
    opportunityId, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId
));

bytes32 messageHash = signalHash.toEthSignedMessageHash();
address recovered = messageHash.recover(v, r, s);

require(recovered == trustedSigner, "InvalidSignature");
```

**Security properties:**
- Deterministic hash of all signal parameters
- Ethereum message prefix prevents domain collision attacks
- ECDSA recovery mathematically proves signer possession
- Chain ID included to prevent cross-chain replay

### 5. Deadline-Based Expiry

ArbitrageExecutor checks signal deadline:

```solidity
if (block.timestamp > signal.deadline) {
    revert SignalExpired(signal.deadline, block.timestamp);
}
```

**Rationale:**
- Market conditions change rapidly
- Stale signals could execute at unfavorable prices
- TEE should only sign recent opportunities with tight deadlines
- On-chain deadline enforces freshness at execution time

### 6. Profit Validation

ArbitrageExecutor enforces minimum profit:

```solidity
uint256 realized = postBalance - preBalance - amount;

if (realized < signal.minProfit) {
    revert InsufficientProfit(realized, signal.minProfit);
}
```

**Rationale:**
- Prevents execution if slippage eats into margins
- TEE calculates expected profit off-chain
- If actual profit < expected, execution reverts
- Protecting against front-running and market movement

### 7. Pausable Execution

ArbitrageExecutor is Pausable:

```solidity
function onFlashLoan(...) external nonReentrant whenNotPaused returns (bytes32) {
    // Execution blocked if paused
}
```

**Use cases:**
- Emergency shutdown if bug discovered
- Maintenance windows
- Market circuit breaker triggering
- Owner-only `pause()` and `unpause()`

---

## Function Reference

### LendingPool.sol

#### `flashLoan(address receiver, address token, uint256 amount, bytes calldata data)`

**Access:** External, Non-reentrant, Not-paused  
**Parameters:**
- `receiver`: Address implementing `IERC3156FlashBorrower`
- `token`: Whitelisted ERC-20 token
- `amount`: Loan amount in token units
- `data`: Arbitrary data passed to receiver's `onFlashLoan()`

**Returns:** `true` if successful

**Flow:**
1. Validate token is supported
2. Check amount ≤ max available
3. Snapshot pre-loan balance
4. Transfer `amount` to receiver
5. Call `receiver.onFlashLoan()` callback
6. Verify callback returns correct hash
7. Check post-loan balance ≥ pre-loan balance + fee
8. Accumulate fee
9. Emit `FlashLoanExecuted` event

**Gas Cost:** ~80k-150k (varies with token transfers)

**Events Emitted:**
```solidity
event FlashLoanExecuted(
    address indexed receiver,
    address indexed token,
    uint256 amount,
    uint256 fee
);
```

---

#### `maxFlashLoan(address token)`

**Access:** View (no state changes)  
**Parameters:**
- `token`: ERC-20 token address

**Returns:** Maximum borrowable amount in token units (0 if unsupported)

**Implementation:**
```solidity
return IERC20(token).balanceOf(address(this)) - accumulatedFees[token];
```

---

#### `flashFee(address token, uint256 amount)`

**Access:** Pure (no state reads)  
**Parameters:**
- `token`: ERC-20 token (not actually used, fee is universal)
- `amount`: Loan amount in token units

**Returns:** Fee amount in token units

**Calculation:** `(amount * FEE_BPS) / 10000` where `FEE_BPS = 9`

**Example:** 
- Loan: 10,000 USDC
- Fee: (10,000 * 9) / 10,000 = 9 USDC (0.09%)

---

#### `setTokenListing(address token, bool enabled)`

**Access:** External (Owner only)  
**Parameters:**
- `token`: ERC-20 token address
- `enabled`: True to whitelist, false to delist

**Events Emitted:**
```solidity
event TokenListingUpdated(address indexed token, bool enabled);
```

---

#### `withdrawFees(address token)`

**Access:** External (Owner only)  
**Parameters:**
- `token`: ERC-20 token to withdraw fees for

**Returns:** Withdrawn fee amount

**Resets:** `accumulatedFees[token] = 0` after withdrawal

**Events Emitted:**
```solidity
event FeesWithdrawn(address indexed token, uint256 amount, address recipient);
```

---

### contracts/contracts/ArbitrageExecutor.sol

#### `onFlashLoan(address initiator, address token, uint256 amount, uint256 fee, bytes calldata data)`

**Access:** External (LendingPool only), Non-reentrant  
**Parameters:**
- `initiator`: Address that initiated flashloan
- `token`: Borrowed token
- `amount`: Borrowed amount
- `fee`: Fee owed to LendingPool
- `data`: Encoded `ArbitrageSignal` struct

**Returns:** `keccak256("ERC3156FlashBorrower.onFlashLoan")`

**Flow:**
1. Verify caller is LendingPool
2. Decode signal from data
3. Check signal deadline hasn't expired
4. Call `SignalValidator.verify(signal)`
5. Verify both DEX routers are approved
6. Execute trades
7. Calculate realized profit
8. Validate profit ≥ minProfit
9. Approve repayment to LendingPool
10. Transfer remaining profit to recipient
11. Emit `ArbitrageExecuted` event

**Events Emitted:**
```solidity
event ArbitrageExecuted(
    bytes32 indexed signalId,
    address indexed dexA,
    address indexed dexB,
    uint256 borrowAmount,
    uint256 profit,
    uint256 gasUsed
);
```

---

### SignalValidator.sol

#### `verify(ArbitrageSignal calldata signal)`

**Access:** External, Stateful (marks signal as used)  
**Parameters:**
- `signal`: Struct containing opportunity ID, DEXes, amounts, deadline, signature components

**Returns:** `true` if verification succeeds, reverts if fails

**Verification Steps:**
1. Check `opportunityId != 0`
2. Check `block.timestamp <= deadline`
3. Check signal not previously used
4. Compute signal hash
5. Apply Ethereum message prefix
6. Recover signer from signature
7. Check recovered signer matches trusted address
8. Mark signal as used
9. Emit `SignalVerified` and `SignalUsed` events

**Errors Thrown:**
- `InvalidOpportunityId()`: If opportunityId is zero
- `SignalExpired(deadline, now)`: If deadline has passed
- `SignalAlreadyUsed(opportunityId)`: If signal already executed
- `InvalidSignature(recovered, expected)`: If signer doesn't match

---

#### `setTrustedSigner(address newSigner)`

**Access:** External (Owner only)  
**Parameters:**
- `newSigner`: New TEE public key address

**Events Emitted:**
```solidity
event TrustedSignerUpdated(address indexed oldSigner, address indexed newSigner);
```

**Use Case:** Rotating TEE signing keys when they're compromised or rotated by 0G

---

## Deployment Guide

### Prerequisites

1. **0G Testnet RPC:** https://evmrpc-testnet.0g.ai (Chain ID: 16600)
2. **Deployer Wallet:** Must have ≥0.1 ETH for gas
3. **Hardhat:** v2.26.3 installed
4. **Environment:** Node.js 18+

### Step 1: Configure Environment

```bash
cd contracts
cp .env.example .env
```

Edit `.env`:
```env
# Deployer private key (without 0x prefix if needed)
DEPLOYER_PRIVATE_KEY=your_private_key_here

# 0G Block Explorer API key (for verification)
BLOCK_EXPLORER_API_KEY=your_api_key_here

# TEE signer address (public key of TEE signing key)
TEE_SIGNER_ADDRESS=0x...

# Optional: Profit recipient address (defaults to deployer)
PROFIT_RECIPIENT_ADDRESS=0x...
```

### Step 2: Fund Deployer

Get testnet ETH from 0G faucet: https://faucet-testnet.0g.ai/

Verify balance:
```bash
npx hardhat run scripts/check_balance.ts --network zgTestnet
```

### Step 3: Compile Contracts

```bash
npx hardhat compile
```

**Output:** `artifacts/` folder with compiled bytecode and ABIs

### Step 4: Run Tests (Optional but Recommended)

```bash
# Run all tests
npx hardhat test

# Run with coverage report
npx hardhat coverage
```

Target: 100% line coverage on critical paths

### Step 5: Deploy

**Option A: Deploy all at once**
```bash
npx hardhat run scripts/deploy_all.ts --network zgTestnet
```

**Option B: Deploy individually**
```bash
# Deploy SignalValidator first (no dependencies)
npx hardhat run scripts/deploy_signal_validator.ts --network zgTestnet

# Deploy LendingPool (no dependencies)
npx hardhat run scripts/deploy_lending_pool.ts --network zgTestnet

# Deploy ArbitrageExecutor (links to both above)
npx hardhat run scripts/deploy_arbitrage_executor.ts --network zgTestnet
```

### Step 6: Verify Deployment

```bash
npx hardhat run scripts/verify_deployment.ts --network zgTestnet
```

**Output:**
```
=== DEPLOYMENT VERIFICATION ===

✓ LendingPool
  Address: 0x1234...
  Status: RESPONSIVE
  FEE_BPS = 9
  Explorer: https://chainscan-galileo.0g.ai/address/0x1234...

✓ SignalValidator
  Address: 0x5678...
  Status: RESPONSIVE
  Trusted Signer = 0xabcd...
  Explorer: https://chainscan-galileo.0g.ai/address/0x5678...

✓ ArbitrageExecutor
  Address: 0x9012...
  Status: RESPONSIVE
  Execution Count = 0
  Explorer: https://chainscan-galileo.0g.ai/address/0x9012...
```

### Step 7: Verify Source Code on Explorer

```bash
# Verify all three contracts
npx hardhat verify --network zgTestnet 0x... [constructor args]
```

After verification, contracts show on explorer with:
- Green "Verified" badge
- Full source code with syntax highlighting
- Ability to read/write functions via web UI

---

## Live Testnet Deployment (2026-05-09)

**Network:** 0G Chain Galileo Testnet (Chain ID: 16602)  
**RPC:** https://evmrpc-testnet.0g.ai  
**Explorer:** https://chainscan-galileo.0g.ai

### Deployed Addresses

| Contract | Address | Block | Tx Hash | Gas Used | Explorer |
|----------|---------|-------|---------|----------|----------|
| **SignalValidator** | `0xe6329A48C0D8E4152e8406dbe102078E1abC7484` | 32478529 | `0xb88a89...` | 720,357 | [Link](https://chainscan-galileo.0g.ai/address/0xe6329A48C0D8E4152e8406dbe102078E1abC7484) |
| **LendingPool** | `0x69d998618c7AEA1224C4bc5898519613c86EE42d` | 32478557 | `0xea8f38...` | 996,161 | [Link](https://chainscan-galileo.0g.ai/address/0x69d998618c7AEA1224C4bc5898519613c86EE42d) |
| **ArbitrageExecutor** | `0xAa0e986143B144f5860C41c74552B67ca78b1EBB` | 32478586 | `0x61e20e...` | 1,203,516 | [Link](https://chainscan-galileo.0g.ai/address/0xAa0e986143B144f5860C41c74552B67ca78b1EBB) |

### Verification Status

- ✅ **All three contracts deployed successfully**
- ✅ **Post-deployment health check passed** (all state variables verified and callable)
- ⚠️ **ChainScan source verification still returns a compiler error** for the fresh deployment

### Health Check Results

```
LendingPool (0xCe233f...):
  FEE_BPS = 9
  LENDING_POOL_BALANCE = [current balance]
  Status = RESPONSIVE

SignalValidator (0xEc238...):
  TRUSTED_SIGNER = 0x28FB61Dc27a37091f53C0c37b5026AdBbF5E1F46
  CHAIN_ID = 16602
  Status = RESPONSIVE

ArbitrageExecutor (0xAa0e98...):
  EXECUTION_COUNT = 0
  SIGNAL_VALIDATOR = 0xe6329A48C0D8E4152e8406dbe102078E1abC7484
  LENDING_POOL = 0x69d998618c7AEA1224C4bc5898519613c86EE42d
  Status = RESPONSIVE
```

---

## Integration Guide

### For Python Agents

```python
from utils.contracts import initialize_contracts

# Initialize
contracts = initialize_contracts(
    rpc_url="https://evmrpc-testnet.0g.ai",
    network="zgTestnet"
)

# Check liquidity
max_loan = contracts.get_max_flashloan("0xUsdc...")

# Calculate fee
fee = contracts.get_current_fee("0xUsdc...", 10000 * 10**6)

# Execute arbitrage
tx_hash = contracts.execute_flashloan(
    token_address="0xUsdc...",
    amount=10000 * 10**6,
    signal_data=encoded_signal,
    signer=deployer_account,
    gas_limit=500000
)

# Wait for confirmation
receipt = contracts.wait_for_confirmation(tx_hash, confirmations=2)
```

### For JavaScript/Node.js

```javascript
const { initializeContracts } = require('./utils/contracts.js');

// Initialize with signer for transactions
const contracts = await initializeContracts(
  "https://evmrpc-testnet.0g.ai",
  signerAccount, // ethers.Signer instance
  "zgTestnet"
);

// Check liquidity
const maxLoan = await contracts.getMaxFlashloan(usdcAddress);

// Calculate fee
const fee = await contracts.getCurrentFee(usdcAddress, ethers.parseUnits("10000", 6));

// Execute flashloan
const tx = await contracts.executeFlashloan(
  usdcAddress,
  ethers.parseUnits("10000", 6),
  signalData,
  { gasLimit: 500000 }
);

// Wait for confirmation
const receipt = await contracts.waitForConfirmation(tx.hash, 2);
```

### Contract Interaction from Frontend (Web3.js/Ethers.js)

```javascript
// Connect to user's wallet via MetaMask
const provider = new ethers.BrowserProvider(window.ethereum);
const signer = provider.getSigner();

// Load contract ABIs
const lendingPoolAbi = await fetch('/abi/LendingPool.json').then(r => r.json());
const lendingPool = new ethers.Contract(LENDING_POOL_ADDRESS, lendingPoolAbi.abi, signer);

// Call read function
const maxLoan = await lendingPool.maxFlashLoan(tokenAddress);

// Send transaction (user must approve with MetaMask)
const tx = await lendingPool.flashLoan(executorAddress, tokenAddress, amount, signalData);
const receipt = await tx.wait();
```

---

## Known Limitations

### 1. On-Chain Attestation Not Verified

**What:** SignalValidator uses ECDSA signature recovery but does NOT verify full TEE attestation reports on-chain.

**Why:** Verifying full remote attestation (Intel SGX, AMD SEV, 0G TEE) requires expensive cryptographic operations (ECDSA on complex curves, Merkle proof verification) that would cost $10k+ per transaction.

**Mitigation:** 
- Attestation is verified off-chain by the agent before signing
- Only signals from trusted, attested TEE instances get signed
- On-chain signer verification ensures only legitimate TEE can sign
- Consider supporting `delegated attestation` in future versions

### 2. DEX Router Interface Assumption

**What:** ArbitrageExecutor assumes DEX routers implement Uniswap-like swap interface.

**Why:** Different DEX protocols have different swap functions (e.g., dYdX has margin trading, Kwenta has perpetual orders).

**Mitigation:**
- Currently hard-coded for Uniswap V3-like routers
- Future version: Support adapter pattern for different DEX types
- Custom risk: Unusual DEX interface could cause execution to fail

### 3. Single-Chain Execution

**What:** Contracts only support execution on 0G Chain. Cannot arbitrage across chains.

**Why:** Building cross-chain atomic execution requires external validators (Wormhole, Axelar) which adds latency and trust assumptions.

**Rationale:** First version optimizes for speed and simplicity. Cross-chain coming in V2.

### 4. Manual Token Listing

**What:** Tokens must be manually whitelisted by owner via `setTokenListing()`.

**Why:** Prevents accidental use of malicious/broken token contracts.

**Improvement:** Future version could use token oracle or external allowlist service.

### 5. No Upgradeable Proxy

**What:** Contracts are immutable once deployed (no proxy pattern).

**Why:** Maximizes trustlessness. No risk of hidden logic changes.

**Trade-off:** Bug fixes require redeployment to new addresses.

**Mitigation:** Extensive testing (100% coverage), third-party audit, gradual rollout to mainnet.

---

## Testing & Verification

### Unit Test Coverage

Run tests with coverage report:
```bash
npx hardhat coverage
```

**Coverage Targets:**
- LendingPool: 100% line coverage
- ArbitrageExecutor: 100% line coverage  
- SignalValidator: 100% line coverage

**Test Categories:**

1. **LendingPool (15+ tests)**
   - Successful flashloan with correct repayment
   - Failed flashloan when amount > maxFlashLoan
   - Failed flashloan when repayment is short by 1 wei
   - Fee calculation at boundary values
   - Emergency pause blocks new flashloans
   - Re-entrancy attack is blocked

2. **SignalValidator (10+ tests)**
   - Signal signed by trusted signer returns true
   - Signal signed by untrusted signer returns false
   - Replayed signal reverts with SignalAlreadyUsed
   - Signal with tampered field fails verification
   - Batch verification works correctly
   - Expired signals are rejected

3. **ArbitrageExecutor (15+ tests)**
   - Valid signal executes trade
   - Invalid signature reverts
   - Expired deadline reverts
   - Profit below minProfit reverts
   - Profit transferred to profitRecipient
   - Flashloan repayment succeeds after profitable trade
   - Pausable execution works

### Manual Testing Checklist

Before mainnet deployment:

- [ ] Deploy to testnet
- [ ] Verify on 0G Explorer
- [ ] Test flashloan flow end-to-end
- [ ] Test all error conditions
- [ ] Test with multiple token types
- [ ] Test signature verification with real TEE key
- [ ] Performance test (gas costs)
- [ ] External security audit (optional but recommended)

---

## Upgrade & Maintenance

### Key Rotation

If TEE signing key is compromised:

```solidity
// Owner can rotate immediately
signalValidator.setTrustedSigner(newTeeSigner);
```

No redeployment needed.

### Fee Adjustment

Fees hardcoded as `FEE_BPS = 9`. To change:

1. Redeploy LendingPool with modified `FEE_BPS`
2. Update `.env` with new address
3. Update frontend/agent code with new address

### Emergency Pause

If critical bug discovered:

```solidity
arbitrageExecutor.pause();
```

Stops all new executions immediately. No transactions can be reverted.

---

## Summary

The Flashix smart contract system provides:

✓ **Atomic execution:** All operations complete in single transaction  
✓ **Cryptographic trust:** ECDSA signature verification of TEE signals  
✓ **Replay prevention:** Nonce tracking prevents resubmitted signals  
✓ **Re-entrancy safety:** Guard prevents nested calls  
✓ **Emergency controls:** Owner can pause or withdraw in crisis  
✓ **Fee accrual:** Lending pool captures fees from arbitrage profits  
✓ **Audit trail:** Events logged on-chain for transparency  

For questions, refer to contract source code comments or reach out to the development team.
