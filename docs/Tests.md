# Tests

Flashix testing covers the full stack: inference determinism, agent reasoning, contract safety, settlement, and end-to-end demo reproducibility.

## Test Coverage

- Unit tests for compute determinism, signal encoding, and validation.
- Agent tests for decision protocol and approval flow.
- Contract tests for flashloan repayment, signal verification, and execution safety.
- Replay tests for inference and trade-quality consistency.
- Integration tests for the pipeline, execution, and settlement lifecycle.
- Smoke tests for the browser demo.

## Run Tests

Frontend:

```bash
npm --prefix frontend test
```

Backend and compute:

```bash
source .venv/bin/activate
pytest -q
```

Contracts:

```bash
cd contracts
npx hardhat test
```

Replay and validation:

```bash
python -m pytest tests/replay/ -v
python tests/run_integration_tests.py
```

## What To Verify

- Signal encoding stays stable across Python and Solidity.
- The compute signature verifier recovers the expected signer.
- The agent never bypasses the approval gate.
- The flashloan path repays principal and fee atomically.
- Settlement reports match the executed trade outcome.
- The UI demo reproduces the seeded opportunity path.

## Performance And Reproducibility

- The smoke script reproduces the core demo in about 10 minutes locally.
- The replay harness is the right check for inference changes before deployment.
- Integration reports and validation reports should be kept in the docs artifacts folders for judge review.

## Related Docs

- [docs/INFERENCE_VALIDATION.md](INFERENCE_VALIDATION.md)
- [docs/INTEGRATION_TESTING.md](INTEGRATION_TESTING.md)
- [docs/0G_Compute.md](0G_Compute.md)
- [docs/0G_Implementation.md](0G_Implementation.md)
