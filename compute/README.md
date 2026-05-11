# Compute Module — Sealed Inference & Cryptographic Trust Chain

## Overview

The Compute module provides deterministic arbitrage analysis in a Trusted Execution Environment (TEE), with cryptographic verification ensuring every signal is genuinely produced by sealed hardware. This document describes the complete five-layer trust chain from hardware attestation through on-chain verification.

---

## Cryptographic Trust Chain Architecture

Flashix's security model is built on five layers of cryptographic trust, each layer building on the previous one:

### Layer 1: TEE Hardware Root of Trust

**What:** Intel SGX or TDX hardware generates an attestation quote that cryptographically proves a specific enclave binary is running on genuine TEE hardware, signed by Intel's Attestation Service (IAS).

**Why:** Without hardware attestation, we cannot distinguish a real TEE from a sophisticated fake. The attestation quote is the anchor that binds all subsequent layers to actual hardware.

**How it works:** When the TEE enclave boots, it calls `sgx_create_report()` with the enclave's public key in the `report_data` field. Intel's attestation infrastructure signs this report, producing an attestation quote that cryptographically proves "this specific code is running on verified hardware right now."

### Layer 2: Enclave Identity Binding

**What:** The TEE's MRENCLAVE measurement (SHA-256 hash of the enclave binary) is registered on-chain in `SignalValidator.sol` so the smart contract knows exactly which code is trusted.

**Why:** Enclave binaries are versioned and can be upgraded. By binding the on-chain verification to a specific MRENCLAVE, we ensure only trusted code produces accepted signals. If the enclave binary is patched, the MRENCLAVE changes and old signals are rejected until the new measurement is registered.

**How it works:** The MRENCLAVE is embedded in the attestation quote. When a TEE key is registered on-chain via `registerTEE(ethAddress, mrenclave)`, the contract stores both pieces. Every signal verification checks `teeRegistrations[signer].mrenclave == EXPECTED_MRENCLAVE`.

### Layer 3: Inference Signing Key

**What:** A secp256k1 ECDSA key pair is generated inside the enclave at first boot and never leaves the hardware boundary. Only the public key and derived Ethereum address are exported and registered on-chain.

**Why:** This key is the "signer of truth" — every inference output is signed with it. By keeping the private key sealed inside the enclave, we ensure the key cannot be stolen or used outside the sealed environment.

**How it works:** On enclave initialization, `EnclaveKeystore.initialize()` generates a fresh secp256k1 key using `eth_account.Account.create()` (which uses `secrets.token_bytes(32)` for cryptographically secure randomness). The private key is immediately encrypted using AES-256-GCM with a key derived from TEE-sealed secrets (in hardware mode via `sgx_seal_data`, in simulation mode via a passphrase). The encrypted keystore is written to disk; only the same enclave can decrypt it.

### Layer 4: Per-Signal Signature

**What:** Every `InferenceOutput` is signed with the enclave's private key before leaving the TEE, creating a cryptographic commitment to the exact inference result.

**Why:** A signature proves two things: (1) the signal came from the holder of the private key, and (2) it has not been modified since signing. Any bit change to the signal invalidates the signature.

**How it works:** The canonical message to sign is constructed by ABI-encoding all relevant fields in a strict order: `eth_abi.encode(['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256'], [...])`. The message is prefixed with the Ethereum signed message prefix and hashed. The enclave signs the hash using its private key via `Account.sign_message()`, producing a signature (r, s, v components). Only the public key can verify this signature, proving the holder of the private key produced it.

### Layer 5: On-Chain Verification

**What:** `SignalValidator.sol` recovers the signer address from the signal signature and checks it against the registered public key, rejecting any signal not provably generated inside the sealed environment.

**Why:** This is the final enforcement point. Before any trade executes, the smart contract cryptographically verifies the signal came from a registered TEE address and that its MRENCLAVE matches the trusted enclave binary.

**How it works:** The contract receives the signal fields and a signature (r, s, v). It reconstructs the exact canonical message hash that was signed (using the same ABI-encoding), calls `ECDSA.recover(hash, v, r, s)` to derive the signer address, then checks:
- `teeRegistrations[recovered].active == true` (key not revoked)
- `teeRegistrations[recovered].mrenclave == EXPECTED_MRENCLAVE` (correct enclave version)
- Nonce is not already used (prevent replay attacks)

If all checks pass, the signal is approved; otherwise it reverts.

---

## Trust Chain Sequence Diagram

```mermaid
sequenceDiagram
    participant Hardware as TEE Hardware<br/>(Intel SGX/TDX)
    participant Enclave as Enclave Code<br/>(Sealed Inference)
    participant Agent as Agent Process<br/>(Untrusted Linux)
    participant Contract as SignalValidator.sol<br/>(On-Chain)
    participant Explorer as Judge / Auditor<br/>(Any Browser)
    
    Hardware->>Enclave: sgx_create_report()
    Note over Enclave: Generate secp256k1 key pair<br/>Encrypt private key<br/>Export public key
    
    Enclave->>Enclave: sgx_seal_data(private_key)
    Note over Enclave: Private key sealed to MRENCLAVE<br/>Cannot be decrypted outside this enclave
    
    Enclave->>Hardware: Generate attestation quote<br/>with public key in report_data
    Hardware->>Hardware: Intel IAS signs quote
    Note over Hardware: Attestation proves:<br/>- This code is running on real hardware<br/>- MRENCLAVE hash of binary
    
    Hardware->>Agent: Return attestation report +<br/>public key + eth_address
    
    Agent->>Contract: registerTEE(ethAddress, mrenclave,<br/>attestationType, signature)
    Note over Contract: Store TEERegistration:<br/>ethAddress → {mrenclave, active=true, registeredAt}
    
    Contract->>Explorer: Emit TEERegistered event<br/>On 0G Explorer
    Note over Explorer: Judges can now see<br/>registered TEE address & MRENCLAVE
    
    Enclave->>Enclave: analyze(ArbitrageInput)
    Note over Enclave: Run inference pipeline<br/>Compute signal fields<br/>Encode canonical message
    
    Enclave->>Enclave: msg_hash = keccak256(encoded)
    Enclave->>Enclave: signature = ECDSA.sign(msg_hash, private_key)
    Note over Enclave: Sign with sealed key<br/>Private key never leaves enclave
    
    Enclave->>Agent: Return InferenceOutput {<br/>decision, profit, fields...,<br/>signature
    }<br/>
    
    Agent->>Agent: AttestationVerifier.verify_inference_response()
    Note over Agent: Local check before submission:<br/>- Recover signer address<br/>- Check expiry<br/>- Verify output hash integrity
    
    Agent->>Contract: submitSignal(signal, signature)
    
    Contract->>Contract: recover signer from signature
    Note over Contract: ECDSA.recover(hash, v, r, s)<br/>→ recovered_address
    
    Contract->>Contract: Check registration
    Note over Contract: teeRegistrations[recovered]<br/>→ {mrenclave, active}
    
    Contract->>Contract: Verify MRENCLAVE matches
    Note over Contract: registration.mrenclave<br/>== EXPECTED_MRENCLAVE
    
    Contract->>Contract: Check nonce (replay protection)
    
    alt All checks pass
        Contract->>Contract: Mark signal as verified
        Contract->>Contract: Emit SignalVerified event
    else Any check fails
        Contract-->>Contract: Revert transaction
        Note over Contract: Signal rejected
    end
    
    Explorer->>Contract: Query verified signals
    Explorer->>Explorer: Decode calldata from tx
    Note over Explorer: Judges can inspect:<br/>- Original signal fields<br/>- Signature<br/>- Recovered signer address<br/>- MRENCLAVE it was verified against
```

---

## Key Generation & Storage

The ECDSA signing key is the crown jewel of the cryptographic system. Its lifecycle:

### Generation (First Boot)

1. **Random Seed:** `EnclaveKeystore.initialize()` calls `eth_account.Account.create()` which uses `secrets.token_bytes(32)` to generate a cryptographically random 32-byte seed.
2. **Key Derivation:** The seed is used to derive a secp256k1 private key.
3. **Address Derivation:** From the private key, the public key and Ethereum address are computed deterministically.
4. **Encryption:** The private key is immediately encrypted using AES-256-GCM:
   - **Hardware mode:** The encryption key is derived from `sgx_seal_data()` which binds decryption to the enclave measurement and platform secrets. The private key can only be decrypted by this exact enclave on this exact machine.
   - **Simulation mode:** The encryption key is derived from a passphrase stored in environment variable `TEE_KEYSTORE_PASSPHRASE`, used for development and testing.
5. **Storage:** The encrypted keystore is written to disk as JSON:
   ```json
   {
     "encrypted_private_key": "0x...",
     "iv": "0x...",
     "tag": "0x...",
     "public_key": "0x04...",
     "eth_address": "0x...",
     "created_at": 1234567890,
     "enclave_measurement": "0x..."
   }
   ```

### Load & Verify (Subsequent Boots)

1. **Load:** Read encrypted keystore from disk.
2. **Decrypt:** Use TEE sealing to recover the decryption key, decrypt the private key.
3. **Verify Integrity:** Recompute the address from the decrypted key and compare to `stored_address`. If mismatch, raise `KeystoreIntegrityError` — this catches corruption or tampering.
4. **Cache:** Hold the decrypted key in memory, accessible only via `sign_message()`.

### Exposure Guarantees

The `EnclaveKeystore` class exposes only:
- `get_public_key() -> str`: The 65-byte uncompressed secp256k1 public key as hex.
- `get_eth_address() -> str`: The Ethereum address derived from the key.
- `sign_message(message_hash: bytes) -> SignedMessage`: The only method that uses the private key. All signing is funnelled through this auditable code path.

The private key is **never** exposed outside the class and **never** written to disk unencrypted.

---

## Signal Signing Protocol

### Canonical Encoding

Every inference output must be encoded identically by both the enclave (Python) and the smart contract (Solidity), or all signatures fail. This is enforced by `signal_encoder.py`:

**Type list (must match Solidity exactly):**
```
['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256']
```

**Field mapping:**
```
[
  bytes32(opportunity_id),           // 32-byte hex, zero-padded
  address(primary_dex),              // Ethereum address
  address(counter_dex),              // Ethereum address
  uint256(borrow_amount * 1e6),      // USDC is 6 decimal places
  uint256(collateral_required * 1e6),
  uint256(expected_profit * 1e6),    // Profit also in micros
  uint32(expiry_timestamp),          // Unix timestamp
  uint256(chain_id)                  // Network identifier
]
```

**Critical Detail:** All USDC-denominated amounts are multiplied by 10^6 before encoding. This matches Solidity's treatment of 6-decimal USDC.

### Message Hashing

1. **Canonical bytes:** `eth_abi.encode(types, values)` produces the ABI-encoded bytes.
2. **Keccak hash:** `keccak256(encoded_bytes)` produces the 32-byte hash.
3. **Ethereum prefix:** The hash is prefixed with `\x19Ethereum Signed Message:\n32` and re-hashed to produce the final message hash.
4. **Signature:** The enclave signs the final message hash using the private key.

### Verification (Off-Chain)

The `AttestationVerifier` class independently verifies every signal before submission:
1. Reconstruct the canonical encoding from signal fields.
2. Hash it identically (Keccak + Ethereum prefix).
3. Call `eth_account.Account.recover_message(message_hash, signature)` to recover the signer address.
4. Assert it matches `TEE_ETH_ADDRESS` from environment.

If this check fails on the agent side, the signal is rejected and never submitted on-chain, preventing wasted gas.

---

## On-Chain Verification Flow

### Signal Submission

The agent calls:
```solidity
SignalValidator.verify(
  ArbitrageSignal calldata signal,
  bytes32 r,
  bytes32 s,
  uint8 v
)
```

### Verification Steps (In Order)

1. **Reconstruct Hash:**
   ```solidity
   bytes32 encoded = abi.encode(
     ['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256'],
     [opportunityId, primaryDex, counterDex, borrowAmount, collateralRequired, expectedProfit, expiryTimestamp, chainId]
   );
   bytes32 msgHash = keccak256(encoded);
   bytes32 ethSignedHash = keccak256(abi.encodePacked(
     "\x19Ethereum Signed Message:\n32",
     msgHash
   ));
   ```

2. **Recover Signer:**
   ```solidity
   address signer = ECDSA.recover(ethSignedHash, v, r, s);
   ```

3. **Check TEE Registration:**
   ```solidity
   TEERegistration memory reg = teeRegistrations[signer];
   require(reg.active == true, "TEE not registered or revoked");
   ```

4. **Verify MRENCLAVE:**
   ```solidity
   require(reg.mrenclave == EXPECTED_MRENCLAVE, "Enclave measurement mismatch");
   ```

5. **Check Nonce:**
   ```solidity
   require(!usedNonces[signal.opportunityId], "Signal already used");
   usedNonces[signal.opportunityId] = true;
   ```

6. **Emit Event:**
   ```solidity
   emit SignalVerified(signal.opportunityId, signer, block.timestamp);
   ```

7. **Return to Caller:** The caller (e.g., `ArbitrageExecutor.sol`) can now safely execute the trade, knowing the signal came from a verified TEE.

### Registration & Revocation

**Register a new TEE:**
```solidity
registerTEE(address ethAddress, bytes32 mrenclave, string calldata attestationType, bytes calldata adminSignature)
```
- Restricted to contract owner.
- Stores the `TEERegistration` struct.
- Emits `TEERegistered` event.

**Revoke a compromised key:**
```solidity
revokeTEE(address ethAddress)
```
- Sets `teeRegistrations[ethAddress].active = false`.
- Signals from that address are immediately rejected.
- No redeployment needed.

---

## How to Verify as a Judge

Follow these steps to independently verify that Flashix's cryptographic model is sound and every executed trade came from the TEE:

### Step 1: Find the Registered TEE Address

Open `deployments/testnet.json` in the repo:
```json
{
  "SignalValidator": "0x...",
  "teeAddress": "0x...",
  "mrenclave": "0x..."
}
```

Note the `teeAddress` and `mrenclave`. This is the TEE's Ethereum address and its enclave measurement.

### Step 2: Verify Registration On-Chain

Open [0G Explorer](https://explorer.0g.ai) and navigate to the `SignalValidator` contract (address from deployments/testnet.json). Look for the `teeRegistrations` mapping and verify:
- `teeRegistrations[teeAddress]` shows `active = true`.
- The stored `mrenclave` matches what you noted in Step 1.
- `registeredAt` is before the first trade you want to inspect.

### Step 3: Inspect an Executed Trade

Find a transaction in the `ArbitrageExecutor` contract that executed a trade. Click on it to view the transaction details. In the "Input Data" section, decode the calldata:
- The signal fields (opportunity_id, primary_dex, counter_dex, borrow_amount, etc.) are visible.
- The signature components (r, s, v) are also visible.

### Step 4: Recover the Signer Locally

Use the included verification CLI to recover the signer address and verify the signature:

```bash
cd compute
python verify_signal.py \
  --opportunity-id <value> \
  --primary-dex <address> \
  --counter-dex <address> \
  --borrow-amount <value> \
  --collateral-required <value> \
  --expected-profit <value> \
  --expiry-timestamp <value> \
  --chain-id <value> \
  --signature <0xrsvhex>
```

The script outputs:
```
Canonical message hash: 0x...
Recovered signer address: 0x...
Signature valid: True
Recovered address matches registered TEE: True
```

### Step 5: Compare to On-Chain State

Verify that the recovered address from Step 4 matches the `teeAddress` from Step 1 and is registered as active in the `SignalValidator` contract. If all three match, the signal is cryptographically proven to have come from the registered TEE and its MRENCLAVE.

### Step 6: Inspect Audit Logs

The `compute/data/audit/signatures_*.jsonl` files contain an append-only audit trail of every signing operation performed by the TEE. For each trade, you can find the corresponding audit record showing:
- `opportunity_id`: Matches the trade.
- `output_hash`: Independently verifiable from signal fields.
- `signing_latency_ms`: Performance metrics.
- `signed_at`: Timestamp of signature creation.

This provides full transparency into the TEE's signing activity.

---

## Security Assumptions & Limitations

### Assumptions (Must Hold for Security)

1. **TEE Hardware Integrity:** Intel SGX or TDX hardware is functioning correctly and TEE-sealed data is not compromised. If hardware is backdoored or faulty, security is voided.
2. **Enclave Code Correctness:** The enclave binary (`enclave.edl` and `host.py`) is free of bugs that could leak the private key or sign unauthorized signals.
3. **MRENCLAVE Accuracy:** The `EXPECTED_MRENCLAVE` constant in `SignalValidator.sol` is the correct hash of the trusted enclave binary and is updated by the owner whenever the enclave is patched.
4. **Signing Key Entropy:** The private key is generated from a cryptographically random 32-byte seed (`secrets.token_bytes(32)`), not from a weak source.
5. **Message Hash Consistency:** The ABI-encoding in Python and Solidity produces identical bytes. This is verified by the `test_encoding_consistency.js` test in CI/CD.
6. **No Double-Spend on Nonce:** The nonce mechanism in `SignalValidator.sol` prevents the same signal (same opportunity_id) from being submitted twice.

### Limitations (Known Constraints)

1. **Simulation Mode Attestation:** In development (simulation mode), the attestation report is generated locally and is **not** signed by Intel IAS. It is clearly flagged `attestation_type: "SIMULATION"` and **cannot** be used on mainnet. Real hardware attestation is required for production.
2. **MRENCLAVE Immutability:** Once an enclave version is deployed and TEE keys are registered, changing the enclave code requires redeployment, new key generation, and on-chain registration of the new MRENCLAVE. There is no way to update the enclave and keep the old signing key — every upgrade requires a new key.
3. **Replay Attack Prevention:** The nonce mechanism only prevents identical opportunities from being processed twice. If an opportunity is legitimately retried with new fields, it is treated as a new opportunity and requires a new nonce. The UI must prevent accidental reuse.
4. **Time-Based Expiry:** Signals include an `expiry_timestamp`. The smart contract does **not** enforce expiry — it is enforced off-chain by the agent. On-chain judges must independently verify the signal has not expired before trusting it.
5. **Private Key Backup/Recovery:** The encrypted keystore can only be decrypted by the same enclave that encrypted it (in hardware mode via sealing). If the enclave is lost, the key is permanently lost and a new key must be generated and registered. There is no backup mechanism.
6. **Performance Overhead:** ECDSA signing and AES encryption add ~10-50ms to each inference signal. Very high-frequency trading may be bottlenecked by signature generation.

---

## Files Reference

- `enclave_keystore.py`: Key generation, encryption, and persistence.
- `attestation.py`: TEE attestation quote generation and formatting.
- `signal_encoder.py`: Canonical message encoding (Python).
- `attestation_verifier.py`: Off-chain signature verification before submission.
- `signature_audit_logger.py`: Audit trail of signing operations.
- `tee_signer.py`: ECDSA signing interface.
- `SignalValidator.sol`: On-chain verification and TEE registration.
- `ArbitrageExecutor.sol`: Executes arbitrage trades after signal verification.
- `register_tee.ts`: Hardhat script to register a new TEE key on-chain.
- `rotate_tee_key.sh`: Bash script for secure key rotation.
- `verify_signal.py`: Judge verification CLI (one-file utility).

---

## Next Steps for Implementation

1. Run `pytest tests/integration/test_crypto_chain.py` to verify the full cryptographic pipeline works end-to-end.
2. For judges: Use `verify_signal.py` to independently verify any executed trade.
3. For operators: Follow `docs/KEY_ROTATION.md` to rotate keys securely during the hackathon.
4. For auditors: Review the audit logs in `compute/data/audit/` for a complete history of all signing activity.
