# Security

Flashix security is built around layered controls, explicit approvals, and auditability.

## Security Model

- Sealed compute prevents untrusted hosts from fabricating signals.
- Canonical signal encoding prevents verifier drift.
- Signature recovery on-chain rejects forged execution instructions.
- Flashloan repayment checks prevent partial settlement.
- Circuit breakers stop execution when market or operational conditions degrade.
- Human overrides provide a last-resort emergency control.

## Key Management

- Never commit deploy keys or TEE secrets.
- Keep local `.env` files out of source control.
- Rotate API keys and signing keys when provisioning changes.
- Use the sealed keystore path for inference signing and verify the recovered address after load.

## Execution Safety

- Simulation must happen before broadcast.
- Signals expire quickly and are rejected if stale.
- Replay protection blocks reused opportunity IDs.
- Router allowlists prevent arbitrary DEX execution.
- Profit floors and gas thresholds prevent low-value trades.

## Operational Checks

- Run the pre-deployment checklist before contracts go live.
- Verify the backend `/health` endpoint before demoing.
- Confirm the frontend is connected to the intended backend.
- Ensure the persistence service is running before generating exports.

## Evidence To Keep

- Deployment manifests.
- Explorer links.
- Decision logs.
- Ledger exports.
- Replay validation reports.
