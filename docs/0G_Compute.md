# 0G Compute

0G Compute is the sealed inference and trust layer that turns a raw opportunity into a cryptographically verifiable execution signal. In Flashix, this layer exists so the system can reason over sensitive market input without exposing the full payload outside the trusted boundary until a signed result is produced.

## What 0G Compute Is Responsible For

The compute layer has four jobs:

1. Load or initialize the sealed ECDSA key material used for signing.
2. Produce a deterministic inference result from the opportunity payload.
3. Bind the result to an attestation report and enclave measurement.
4. Export a signal that the on-chain validator can verify without trusting the off-chain host.

The relevant modules live under [compute/](../compute/).

## Trust Chain

Flashix’s compute trust model is deliberately layered so each step can be audited independently.

### 1. Hardware or Simulation Attestation

The attestation path starts in [compute/attestation.py](../compute/attestation.py).

- `AttestationGenerator` produces an `AttestationReport` for a given enclave public key.
- Supported modes are `simulation`, `sgx_hardware`, and `tdx_hardware`.
- In simulation mode, the report still includes the fields that downstream code expects, but the `attestation_type` is explicitly marked as `SIMULATION`.
- The report includes `mrenclave`, `mrsigner`, `public_key`, `eth_address`, `isvsvn`, `quote_body`, and `ias_signature`.

Why this matters:

- The attestation report is the provenance record for the signing identity.
- The enclave measurement makes it possible to bind a signer address to a specific code image.
- Even in local development, the shape of the report mirrors the production trust boundary.

### 2. Sealed Key Management

The signing key lifecycle lives in [compute/enclave_keystore.py](../compute/enclave_keystore.py).

- `EnclaveKeystore.initialize()` either loads an existing encrypted keystore or generates a new secp256k1 key pair.
- The private key is encrypted with AES-256-GCM before being written to disk.
- Simulation mode derives the encryption key from `TEE_KEYSTORE_PASSPHRASE` using PBKDF2.
- Hardware mode is designed to derive the key from TEE-sealed data, but the current repository implementation falls back to simulation mode for local development.
- The keystore metadata stores the encrypted private key, IV, auth tag, public key, Ethereum address, creation time, and enclave measurement.

Operational guarantees:

- The private key is never exposed by the class API.
- `get_public_key()` and `get_eth_address()` are read-only accessors.
- `sign_message()` is the only public path that uses the private key.
- When a keystore is loaded, the recovered key must regenerate the same address or the load is rejected.

### 3. Canonical Signal Encoding

Signal serialization is handled by [compute/signal_encoder.py](../compute/signal_encoder.py).

The encoder is the source of truth for how a signal becomes bytes before hashing and signing.

Canonical ABI layout:

```text
['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256']
```

Field mapping:

- `opportunity_id` -> `bytes32`
- `primary_dex` -> `address`
- `counter_dex` -> `address`
- `borrow_amount` -> `uint256`
- `collateral_required` -> `uint256`
- `expected_profit` -> `uint256`
- `expiry_timestamp` -> `uint32`
- `chain_id` -> `uint256`

Important details:

- Amounts are converted into micro-units before encoding.
- The encoder accepts both `expected_profit_usdc` and `expected_profit` for convenience.
- `encode_for_signing_with_hash()` returns both the ABI bytes and the Keccak-256 digest.
- `verify_roundtrip()` checks that encode/decode stays stable.

This encoding step matters because the Solidity verifier reconstructs the exact same hash. If the Python encoder and Solidity contract ever drift apart, verification fails by design.

### 4. Local Signature Verification

The offline verification path lives in [compute/verify_signal.py](../compute/verify_signal.py).

- The CLI reconstructs the canonical hash from a JSON payload.
- It recovers the signer from the provided signature.
- If `--expected-address` is supplied, it prints whether the recovered signer matches the expected TEE address.

This utility is useful for judges and operators because it lets them verify a signal without needing to submit it on-chain.

## Live 0G Compute Access

When you use the hosted 0G Compute provider instead of the local simulation path, the goal is to authenticate the request, pin the provider identity, and verify the returned signature shape before any signal is trusted.

Typical environment variables:

- `TEE_MODE=0g-compute`
- `TEE_ENDPOINT` points at the provider HTTPS endpoint.
- `TEE_API_KEY` stores the provider-issued secret.
- `TEE_ATTESTATION_CERT_PATH` points at the pinned certificate.

Operational flow:

1. Register with the provider and obtain credentials.
2. Store the API key in a local secret file or secret manager.
3. Pin the attestation certificate before sending live requests.
4. Validate the recovered signer against the expected TEE address.
5. Fail closed if the provider response does not match the expected signature shape.

Why this matters:

- It mirrors the production path used by the live TEE workflow.
- It keeps the local and remote compute behaviors aligned.
- It makes it possible to reason about provider outages, latency spikes, and credential rotation without rewriting the rest of the stack.

## End-to-End Compute Flow

The typical lifecycle looks like this:

1. The agent or pipeline produces an opportunity payload.
2. The TEE loads or initializes its keystore.
3. The payload is encoded canonically.
4. The message hash is derived with Keccak-256.
5. The sealed private key signs the hash.
6. An attestation report ties the public key back to the enclave identity.
7. The signed signal is sent to the on-chain validator.

That sequence gives Flashix both privacy and verifiability: the host can inspect the result, but it cannot forge a valid signature without the sealed key.

## What Gets Verified On-Chain

The on-chain verifier expects the following properties:

- The signal comes from a trusted signer address.
- The canonical hash matches the exact ABI layout used by the encoder.
- The signal has not expired.
- The opportunity ID has not already been consumed.
- The trusted signer is still registered and has not been rotated or revoked.

In practice, this means the compute layer must produce deterministic output and the contract must reject anything stale, replayed, or unsigned.

## Evidence And Audit Trail

Flashix keeps the compute proof chain visible for operators and reviewers:

- Attestation data proves which enclave identity produced the signal.
- The keystore metadata captures the signing identity and creation time.
- The signal encoder guarantees a stable byte representation.
- The verification CLI lets a reviewer reconstruct the exact hash.
- The frontend `Compute` page surfaces the linked request, validation status, and proof artifact.

## Development Notes

- Use simulation mode for local testing.
- Keep `TEE_KEYSTORE_PASSPHRASE` stable across local runs if you want the encrypted keystore to reload.
- Treat `signal_encoder.py` as a contract boundary, not a convenience helper.
- If you change the signal schema, update both the encoder and the Solidity verifier together.

## Related Files

- [compute/attestation.py](../compute/attestation.py)
- [compute/enclave_keystore.py](../compute/enclave_keystore.py)
- [compute/signal_encoder.py](../compute/signal_encoder.py)
- [compute/verify_signal.py](../compute/verify_signal.py)
