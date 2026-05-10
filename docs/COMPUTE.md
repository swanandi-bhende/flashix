# Flashix Compute Integration (TEE)

This document describes the sealed inference integration using 0G Compute (testnet) and a local TEE sandbox.

## Architecture

Sequence: MemPoolListener → PayloadBuilder → TEEClient → [0G Compute TEE Enclave: ArbitrageAnalyzer → SignedSignal] → AttestationVerifier → ArbitrageAgent → SmartContract

## Why TEE Matters

Without sealed compute, mempool data and trading signals are exposed to the compute provider; with TEE the provider can prove the exact code ran on the data without seeing plaintext.

## Configuration reference

- `TEE_MODE`: `local` or `0g-compute` (default: `local` for development)
- `TEE_ENDPOINT`: Full HTTPS URL of the 0G Compute TEE inference endpoint
- `TEE_API_KEY`: API secret used for request signing (HMAC)
- `TEE_ATTESTATION_CERT_PATH`: Path to provider attestation certificate
- `TEE_REQUEST_TIMEOUT_MS`: Request timeout in milliseconds (default: 5000)
- `TEE_SIGNATURE_VALIDATION`: `true`/`false` whether to reject unsigned responses

## Operational Runbook

- Switch from local to 0G: set `TEE_MODE=0g-compute` and populate `TEE_ENDPOINT`/`TEE_API_KEY`/`TEE_ATTESTATION_CERT_PATH`.
- Rotate API key: generate new key, update secrets store and `.env`, verify requests succeed, then revoke old key.
- COMPUTE_UNAVAILABLE alert: set agents to halt new processing and notify ops via webhook.
- Re-validate attestation after certificate rotation: run `python -m compute.attestation_verifier --refresh` (helper script planned).

## Known limitations

- Local Open Enclave simulation does not provide real hardware attestation.
- Attestation verification depends on Intel/0G attestation services reachable from the host.
- Model accuracy depends on training dataset quality.
