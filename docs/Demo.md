# Demo

This guide walks through the Flashix user interface and the recommended demo story. Use the hosted demo first, then fall back to local execution when you need to inspect logs or source behavior.

## Primary Demo Link

Open the live app here: [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/)

## Demo Goals

The demo is designed to show five things clearly:

1. Market and pipeline state are visible in a single dashboard.
2. Opportunities can be simulated, approved, rejected, and traced.
3. Risk controls can pause or block execution when needed.
4. Execution is gated by a simulation step before broadcast.
5. Settlement evidence and exports remain available for audit.

## Quick Demo Setup

If you are running locally, start the supporting services first:

```bash
python3 scripts/tee_service.py
source .venv/bin/activate
python -m agent.backend_app
npm --prefix frontend run dev
```

Then open the deployed app or the local Vite URL.

If you want the shortest possible live walkthrough, use the deployed app first, then repeat locally only for replay or log inspection.

## Page-by-Page Walkthrough

### 1. Dashboard

The dashboard is the best starting point because it shows the current system state, the main action shortcuts, and the recent activity feed.

What to look for:

- Pipeline state and queue health.
- Total opportunities and execution health.
- Risk status and market data freshness.
- Quick actions to open each sub-page.
- `Run Demo` and `Run Full Demo` buttons.

What to do:

1. Open the Dashboard.
2. Read the health cards across the top.
3. Click `Run Demo` to seed or replay the deterministic demo scenario.
4. Use `Guided Tour` first if you want a narrated 3-step overlay before the demo starts.
5. If the tour opens, use `Next` to move through the prompts, `Back` if you want to revisit a step, and `Start Demo` on the final step.
6. If you want the fastest possible run, click `Run Full Demo` or `Skip and Run Demo` from the tour overlay.

What to enter:

- No text input is needed on this page.
- Leave the metric cards alone; they are read-only.
- If you are presenting, keep the dashboard on screen until the opportunity queue updates.

### 2. Pipeline

The Pipeline page shows the lifecycle stages that the demo opportunity moves through.

What to look for:

- The seeded demo item, usually `OPP-9999`.
- Stage transitions across the pipeline.
- The trace and playback controls.

What to do:

1. Open Pipeline from the dashboard.
2. Make sure the selected item is the seeded demo item `OPP-9999`. If you need to force it, open the page with `?item=OPP-9999`.
3. Click `Run Pipeline Demo` to create the step-by-step lifecycle record.
4. Click `Replay lifecycle` to start the staged playback.
5. Use `Play replay` to advance automatically, or `Pause replay` if you want to explain a step before moving on.
6. Click `Replay lifecycle` again if you want to reset the flow and watch it from the beginning.

What to enter:

- No form fields are required here.
- The only value that matters is the selected item, and the standard demo item is `OPP-9999`.
- If the page shows a different item, use the query string or return to the dashboard and run the demo again.

### 3. Opportunities

This page is the operator queue. It is where candidates are evaluated before execution.

What to look for:

- Queue size, pending count, executing count, and rejected count.
- Expected profit, risk, freshness, and disposition for each candidate.
- The full action trail on each row.

What to do:

1. Open Opportunities.
2. If you want extra queue activity, click `Simulate 3 Mempool Events` or `Simulate 10` before touching a row.
3. Pick the seeded demo item `OPP-9999` first so the rest of the walkthrough stays deterministic.
4. Click `Simulate` on that row to run the pre-flight check.
5. Wait for the simulation modal, read the result, then click `Close`.
6. Click `Approve` only after simulation has passed.
7. If you want to demonstrate a rejection path, click `Reject`, type a reason into the `Rejection reason for audit` box, then click `Confirm Reject`.
8. Click `Open Trace` to inspect the recorded decision steps for the same item.
9. Use `View Details` if you want to jump into the dedicated opportunity page instead of staying in the queue.

What to enter:

- For rejection, type a short audit reason such as `freshness below threshold`, `risk limit exceeded`, or `demo only`.
- Leave the reason blank only if you want the UI to store the fallback value `operator_rejected`.
- Do not change the opportunity values themselves; the point of the demo is to show the seeded item and its deterministic path.

### 4. Risk

The Risk page shows circuit breakers, portfolio limits, and operator overrides.

What to look for:

- Overall risk status.
- Active or triggered breakers.
- Portfolio limit bars for loss, leverage, position count, and slippage.
- Human overrides and their persisted records.

What to do:

1. Open Risk.
2. Review the circuit breakers and the portfolio limits before changing anything.
3. If a breaker is in warning or triggered state, click `Acknowledge` on that breaker only if you want to show the operator acknowledgement flow.
4. Click `Details` or `Affected` to show the breaker information and impacted trades.
5. In the Human Override Controls section, click `Clear Override` if you want to demonstrate how an active override is removed.
6. If you want to show the emergency path, click `Trigger Emergency Stop`, enter a reason, and then click `Confirm Emergency Stop`.

What to enter:

- For an emergency stop, use a reason like `manual pause for demo` or `market feed degraded`.
- For a normal breaker acknowledgement, no text entry is needed.
- Leave the portfolio limit cards alone unless you are specifically demonstrating risk state changes.

### 5. Execution

The Execution page is where the trade becomes real. It includes the pre-flight simulation, gas analysis, broadcast status, and proof links.

What to look for:

- The current execution state.
- Simulation pass or failure status.
- Gas estimate and profit-after-gas display.
- Broadcast hash and on-chain proof links.
- The proof card showing the deployed 0G contracts.

What to do:

1. Open Execution.
2. Click `Simulate` first and wait for the simulation state to change to passed.
3. Check that the `Profit After Gas` card stays green before moving forward.
4. Click `Broadcast` only after the candidate is approved and simulation has passed.
5. If the execution state becomes `failed` or `partial_success`, use `Retry Execution` to show the recovery path.
6. When a transaction hash appears, click the copy icon to copy it, then click `View on Chain` or the external-link icon to open the proof page.
7. If you need to inspect the RPC payload, click `View / Replay`, then use `Replay Now` or `Download Receipt` as needed.

What to enter:

- The `Replay Endpoint` field defaults to `https://rpc.ankr.com/eth_goerli`.
- Leave that value alone for a standard demo replay.
- Only change the replay endpoint if you are intentionally testing a different RPC target.

### 6. Settlement

The Settlement page summarizes realized PnL, unrealized exposure, repayment state, and export links.

What to look for:

- Overall portfolio status.
- Realized PnL versus unrealized PnL.
- Open positions and repayment obligations.
- `Last Export` link when a ledger export exists.

What to do:

1. Open Settlement.
2. Review the realized and unrealized summaries at the top before making any changes.
3. Click `Compare` on a realized PnL row if you want to show the expected-versus-realized analysis.
4. If an open position is present, click `Close`, read the liquidation confirmation modal, and then click `Close Position` if you want to demonstrate the close flow.
5. If a repayment is still outstanding, click `Record Repayment` to settle the remainder.
6. Click `Export Report` to open the export controls.
7. Leave the default last-24-hours window in place for the standard demo, or adjust the start and end timestamps if you want a narrower report.
8. Click `Generate & Download` to create the ledger export.
9. Use `Cancel` if you only wanted to show the export UI without producing a file.

What to enter:

- The export fields are `datetime-local` inputs.
- For the standard demo, keep the auto-filled last-24-hours range.
- If you want to show a smaller export, set the start time to a few hours before now and the end time to the current time.

### 7. Market Data

The Market Data page explains why the system trusts or distrusts the current input feed.

What to look for:

- Source health.
- Freshness timing.
- Fallback reliability.
- Persisted snapshot and source URLs.

What to do:

1. Open Market Data.
2. Click `Refresh Feeds` once so the snapshot and fallback data are current.
3. Click `View Source Breakdown` on the `Pyth` feed first to show the most detailed source panel.
4. Use the source pills (`Pyth`, `Chainlink`, or the fallback source) to switch the focused feed if you want to compare providers.
5. Click `Open Fallback Events` to jump straight to the failover history.
6. Check `Trust for execution?` before moving to Execution; it should show `TRUSTED` for the standard demo.

What to enter:

- No manual values are required on this page.
- If you are explaining the data path, keep the focused source on `Pyth` because it is selected by default.
- If the page looks stale, refresh once before proceeding rather than changing any values.

### 8. Compute

The Compute page is the evidence screen for sealed inference and signature verification.

What to look for:

- Inference request history.
- Validation and signature status.
- Trace linking to pipeline items.
- Signed proof artifacts and their URLs.

What to do:

1. Open Compute.
2. Find the request linked to the seeded pipeline demo. That request should match the same item you used in Pipeline.
3. Click `Verify Payload` on the latest request first so you can show the TEE validation path.
4. In the verification modal, read the pass result, then click `Close`.
5. Click `Replay Inference` if you want to demonstrate deterministic reprocessing.
6. Click `Open Trace` to show the linked trace record.
7. Click `Inspect Signature` to show the signer metadata and verification details.
8. Click `Show proof` on the linked proof card to open the TEE proof modal.
9. If an artifact link is shown, click `View artifact` to open the signed output in a new tab.

What to enter:

- No manual fields need to be filled on the standard compute path.
- Use the already linked request ID from the seeded demo rather than typing a custom one.
- The proof modal is read-only, so the demo is purely about inspection, not data entry.

## Recommended Demo Flow

Follow this order for the cleanest presentation:

1. Dashboard: launch the demo and explain the current system state.
2. Pipeline: show the seeded opportunity moving through the lifecycle.
3. Opportunities: simulate and approve the candidate.
4. Execution: confirm simulation, gas, and broadcast.
5. Settlement: show realized PnL and export evidence.
6. Risk: confirm no breaker was violated, or explain the override if there was one.
7. Market Data and Compute: close with freshness and proof artifacts.

## What Judges Should Notice

- The demo is deterministic enough to replay.
- Every important action has an audit trail.
- The system does not broadcast without simulation.
- Risk decisions and settlement outcomes remain visible after the fact.
- The deployed app at [https://flashix-mu.vercel.app/](https://flashix-mu.vercel.app/) is the easiest way to review the UX.

## Automated Reproduction

If you want to reproduce the demo without clicking through the UI manually, run the smoke script after starting the local services:

```bash
node frontend/scripts/e2e/smoke_demo.js
```

Use this when you need a repeatable run for testing or judge verification.

## Troubleshooting During the Demo

### The demo link loads, but the data looks stale

Refresh the page once, then compare the market data freshness card with the activity feed.

### Compute proofs are missing

Make sure the pipeline demo has been run first, because Compute depends on the linked request history.

### Settlement does not show an export

Confirm that `scripts/tee_service.py` is running and that a settlement action has been completed.

### The browser shows a backend error

Check that the FastAPI backend is running and that the frontend is pointing at the correct API base URL.

## Suggested Next Step

After the demo, read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how the pages, backend routers, and persistence flow fit together.
