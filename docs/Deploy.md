# Deploy

This guide covers the public deployment surface for Flashix: frontend hosting, backend runtime, contract deployment, and proof artifact handling.

## Public Hosting Layout

- Frontend: Vercel or equivalent static hosting.
- Backend: Render, Railway, or another Python host that supports FastAPI.
- Contracts: 0G testnet or mainnet through Hardhat.
- Evidence: deployment manifests, explorer links, and ledger exports persisted to the demo storage service.

## Backend Deployment

1. Create a Python 3.12+ service.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the app with the backend entry point used by the repo.
4. Set environment variables for persistence, RPC access, signer address, and any provider tokens.
5. Confirm `/health` returns `ok` before exposing the service.

Recommended runtime variables:

- `PERSISTENCE_URL`
- `RPC_URL`
- `TEE_SIGNER_ADDRESS`
- `GEMINI_API_KEY`
- `PINATA_JWT`

## Frontend Deployment

1. Deploy the `frontend/` workspace to Vercel.
2. Configure the frontend to point at the deployed backend URL.
3. Verify the dashboard loads and the main routes resolve.
4. Confirm the deployed app at [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/) matches the expected UX.

## Contract Deployment

Before deploying contracts:

1. Run the testnet checklist.
2. Compile the contracts.
3. Validate the trusted signer address.
4. Confirm the router and pool configuration for the target chain.

After deployment:

- Record the transaction hashes.
- Update the deployment manifest.
- Save the explorer links.
- Re-check the UI proof cards against the deployed addresses.

## Testnet And Mainnet Notes

- Testnet should be used for validation and judge demos.
- Mainnet should only be used after the deployment checklist and replay validation pass.
- The deployment flow should always preserve the audit trail: address, hash, gas, block number, and explorer URL.

## CI And Secrets

- Do not commit private keys.
- Store contract deploy keys in a secret manager.
- Keep explorer verification keys separate from runtime service secrets.
- Rotate keys if a deployment credential is reused beyond its intended window.

## Deployment Artifacts To Keep

- Deployment manifests under `contracts/deployments/`.
- Contract ABIs and generated types.
- Explorer verification links.
- Screenshots of the verified contract pages.
- A summary of any deploy-time warnings or manual overrides.

## Related Docs

- [docs/CONTRACTS.md](CONTRACTS.md)
- [docs/TESTNET_VALIDATION.md](TESTNET_VALIDATION.md)
- [docs/PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md)
- [docs/MAINNET_HARDENING.md](MAINNET_HARDENING.md)
