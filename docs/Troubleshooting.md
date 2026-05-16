# Troubleshooting

This page collects the most common operational failures across compute, mempool, contracts, and the demo UI.

## Common Issues

- Frontend build errors: reinstall dependencies and rebuild the Vite app.
- Backend import errors: confirm the virtual environment is active.
- Hardhat chain ID mismatch: confirm the selected network matches the configured RPC.
- Missing export links: ensure the persistence service is running.
- Stale market data: refresh the feeds and confirm the oracle pipeline is healthy.
- Mempool disconnects: check provider credentials and WebSocket URLs.
- Compute failures in live mode: verify `TEE_MODE`, endpoint reachability, and attestation certificate path.
- Signal verification failures: inspect the canonical encoder and signer recovery path.
- Flashloan repayment errors: inspect the pool balance, fee math, and callback data.

## Quick Checks

1. Confirm the backend health endpoint responds.
2. Confirm the frontend route you are opening exists in the router.
3. Confirm the persistence service is running before you expect exports.
4. Confirm the compute and contract configuration match the target environment.
5. Confirm the deployment manifests contain the expected addresses.

## How To Debug

- Check the backend logs for request and decision flow failures.
- Check the TEE or compute logs for attestation or signing issues.
- Check the browser console for route or runtime errors.
- Re-run the targeted test or replay harness when a logic change is suspected.
- Compare the local behavior with the deployed app when the UI state looks inconsistent.


