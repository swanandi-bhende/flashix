# 0G Compute Access & TEE Credentials

This document records how to obtain and store TEE-enabled 0G Compute credentials for Flashix (testnet).

Steps to obtain credentials
- Register a developer account at https://docs.0g.ai/ and follow the Compute Network registration flow.
- Apply for a TEE-enabled inference endpoint (premium tier). Note provisioning delays may apply.
- When approved, generate an API key pair and download the attestation certificate (`tee-attestation.pem`).

Storage and local paths
- Store `tee-attestation.pem` and any private keys under `/certs/` (this directory is gitignored).
- Env placeholders: `TEE_ENDPOINT`, `TEE_API_KEY`, `TEE_ATTESTATION_CERT_PATH`.

Recorded testnet values (examples; replace after provisioning)
- Endpoint URL: https://compute-testnet.0g.ai/v1/tee/infer
- API version: v1
- Supported model formats: `pkl` (sklearn/xgboost), `onnx` (optional)
- Max payload size: 1MB (verify with provider)
- Rate limits: documented in provider dashboard (record here when approved)

Security Guarantees
- Deterministic execution: model version pinned by sha256 hash; deterministic RNG seeding enforced inside enclave.
- Zero egress: enclave has no outbound network access; host manages I/O and returns signed responses.

Files to check-in
- Add placeholders to `.env.example` and document local/0g toggle.
