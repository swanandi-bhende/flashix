# 0G Compute Access & TEE Credentials

This document records how to obtain and store TEE-enabled 0G Compute credentials for Flashix.

Use it as the source of truth for the live endpoint, API key, and attestation certificate once provisioning completes.

Steps to obtain credentials
- Register a developer account at https://docs.0g.ai/ and follow the Compute Network registration flow.
- Apply for a TEE-enabled inference endpoint (premium tier). Note provisioning delays may apply.
- When approved, generate an API key pair and download the attestation certificate (`tee-attestation.pem`).

Storage and local paths
- Store `tee-attestation.pem` and any private keys under `/certs/` (this directory is gitignored).
- Env placeholders: `TEE_ENDPOINT`, `TEE_API_KEY`, `TEE_ATTESTATION_CERT_PATH`, `TEE_MODE`.

Recorded testnet values (examples; replace after provisioning)
- Endpoint URL: https://router-api-testnet.integratenetwork.work/v1/chat/completions for Router mode, or the provider-specific HTTPS endpoint shown in the dashboard for direct TEE access.
- API version: v1
- Supported model formats: `pkl` (sklearn/xgboost), `onnx` (optional)
- Max payload size: record the provider limit here after approval.
- Rate limits: record requests per minute and tokens per second from the dashboard here.
 
Provider-specific testnet info (example)
- Provider name: `TeeML` (qwen-2.5-7b-instruct)
- Provider address: `0xa48f01287233509FD694a22Bf840225062E67836`
- Example service URL (from provider dashboard): `https://compute-network-6.integratenetwork.work/v1/proxy`
- Pricing (example): In: 0.31 0G / 1M tokens, Out: 1.24 0G / 1M tokens

Quick CLI steps (testnet) — run locally; do NOT commit secrets
1. Fund your testnet wallet and set `PRIVATE_KEY` in shell
2. Deposit to your account (example):
```
0g-compute-cli deposit --amount 5
```
3. Transfer funds to provider and acknowledge:
```
0g-compute-cli transfer-fund --provider 0xa48f01287233509FD694a22Bf840225062E67836 --amount 5
0g-compute-cli inference acknowledge-provider --provider 0xa48f01287233509FD694a22Bf840225062E67836
```
4. Get the app secret for your app (do not paste into git):
```
0g-compute-cli inference get-secret --provider 0xa48f01287233509FD694a22Bf840225062E67836
# stores/prints an `app-sk-...` secret and service URL
```
5. Save the `app-sk-...` into `.env.local` as `TEE_API_KEY` and set `TEE_MODE=0g-compute` and `TEE_ENDPOINT` to the provider service URL.

Credential placeholders to copy into your local environment
- `TEE_ENDPOINT`: provider service URL
- `TEE_API_KEY`: `app-sk-...`
- `TEE_ATTESTATION_CERT_PATH`: path to `tee-attestation.pem`
- `TEE_MODE`: `local` or `0g-compute`

Example curl test (replace `<SECRET>` and endpoint):
```
curl https://compute-network-6.integratenetwork.work/v1/proxy/chat/completions \
	-H "Content-Type: application/json" \
	-H "Authorization: Bearer app-sk-<SECRET>" \
	-d '{"model":"qwen/qwen-2.5-7b-instruct","messages":[{"role":"user","content":"Hello"}]}'
```

Security note: treat `app-sk-...` as a secret; store in `.env.local` or a secrets manager and never commit.

Security Guarantees
- Deterministic execution: model version pinned by sha256 hash; deterministic RNG seeding enforced inside enclave.
- Zero egress: enclave has no outbound network access; host manages I/O and returns signed responses.

Files to check-in
- Add placeholders to `.env.example` and document local/0g toggle.
