# Inference Validation

Flashix uses a deterministic replay framework to check inference changes before deployment.

## What It Tests

The replay suite validates three financial properties:

- Determinism: identical inputs must always produce identical outputs.
- Accuracy: estimated profit must match realized P&L within 1% when ground truth exists.
- Signal quality: high-confidence signals must outperform low-confidence signals by at least 2% on average.

The framework also covers extreme scenarios such as flash crashes, funding-rate spikes, zero liquidity, stale prices, gas spikes, and network congestion.

## Latest Report

The latest validation summary is written to `docs/validation_reports/latest.json` and historical Markdown reports are stored in `docs/validation_reports/`.

## Local Run

Run the replay suite locally with:

```bash
python -m pytest tests/replay/ -v
```

The harness can also be executed directly:

```bash
python tests/replay/replay_harness.py --ci-mode
```

## Deployment Meaning

If `deployment_recommended` is `false`, Flashix treats the inference change as unsafe for deployment.
That means the model is either non-deterministic, too inaccurate, or not producing confidence scores that separate better trades from worse ones.

This check is enforced before CI/CD deploys and before manual contract deployments, so new inference logic must pass replay validation before it can reach mainnet.
