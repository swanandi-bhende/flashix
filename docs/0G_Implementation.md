# 0G Implementation

This document describes the on-chain side of Flashix: how the trusted signal is verified, how flashloans are issued, how trades execute atomically, and how execution evidence is emitted for later settlement and audit.

The Solidity sources live in [contracts/contracts/](../contracts/contracts/) and the generated ABI and deployment artifacts live under [contracts/](../contracts/).

## Contract Roles

### SignalValidator

Source: [contracts/contracts/SignalValidator.sol](../contracts/contracts/SignalValidator.sol)

`SignalValidator` is the trust gate between 0G Compute and execution.

What it does:

- Accepts a structured `ArbitrageSignal`.
- Reconstructs the canonical signal hash with `abi.encode(...)`.
- Applies the Ethereum signed-message prefix.
- Recovers the signer from `(v, r, s)`.
- Checks the recovered signer against the trusted TEE address.
- Rejects expired or already-used signals.
- Marks a signal as used to prevent replay.

Important state:

- `trustedSigner` stores the current verified TEE address.
- `usedSignals` tracks opportunity IDs that have already been consumed.
- `chainId` is stored for domain separation.

Important events:

- `SignalVerified`
- `SignalUsed`
- `TrustedSignerUpdated`

Failure modes:

- `InvalidSignature` when the recovered signer does not match the trusted address.
- `SignalExpired` when the deadline has passed.
- `SignalAlreadyUsed` when the opportunity ID was already consumed.
- `InvalidOpportunityId` when the signal is empty.

### LendingPool

Source: [contracts/contracts/LendingPool.sol](../contracts/contracts/LendingPool.sol)

`LendingPool` is the ERC-3156 flashloan provider used to source capital for arbitrage execution.

What it does:

- Maintains token liquidity for supported assets.
- Calculates the fee for each flashloan.
- Transfers the borrowed token to the borrower.
- Calls the borrower callback.
- Verifies repayment plus fees before completing the transaction.
- Tracks accumulated fees for later withdrawal.

Important state:

- `supportedTokens` marks which ERC-20 tokens can be borrowed.
- `accumulatedFees` stores collected fees per token.

Important configuration:

- `FEE_BPS` is currently 9 basis points.
- The constructor enables example stablecoins by default, but the token list should be adjusted for the deployment network.

Failure modes:

- `UnsupportedToken` if the asset is not whitelisted.
- `InsufficientLiquidity` if the requested amount exceeds available capital.
- `InsufficientRepayment` if the callback does not restore the pool balance.
- `InvalidFlashLoanReturn` if the borrower callback does not return the expected hash.

### ArbitrageExecutor

Source: [contracts/contracts/ArbitrageExecutor.sol](../contracts/contracts/ArbitrageExecutor.sol)

`ArbitrageExecutor` coordinates the full arbitrage lifecycle once a signal has been verified.

What it does:

- Receives the flashloan callback from `LendingPool`.
- Validates that the calling pool and validator are configured.
- Decodes the execution signal and optional trace ID.
- Checks that both DEX routers are approved.
- Executes the arbitrage path.
- Measures realized profit.
- Repays the loan plus fee.
- Sends remaining profit to the configured recipient.
- Emits execution and trace events for the UI and settlement layer.

Important state:

- `lendingPool` is the configured flashloan source.
- `signalValidator` is the on-chain verification contract.
- `profitRecipient` receives realized profit.
- `approvedRouters` is the allowlist for DEX endpoints.
- `traceIdsByOpportunity` binds a signal ID to a reasoning trace.

Important events:

- `ArbitrageExecuted`
- `TraceLinked`
- `RouterApprovalUpdated`
- `ProfitRecipientUpdated`
- `LendingPoolUpdated`
- `SignalValidatorUpdated`

Failure modes:

- `SignalVerificationFailed` if the signal is not accepted.
- `SignalExpired` if the execution deadline has passed.
- `UnapprovedRouter` if either DEX address is not on the allowlist.
- `InsufficientProfit` if realized profit falls below the threshold.
- `LendingPoolNotConfigured` or `SignalValidatorNotConfigured` when setup is incomplete.

## End-to-End Execution Flow

The on-chain flow is intentionally simple and strict:

1. The TEE signs a canonical signal off-chain.
2. The agent packages the signal for execution.
3. `ArbitrageExecutor` receives the flashloan callback.
4. `SignalValidator` verifies the signal and marks it used.
5. The executor checks that both routers are approved.
6. The trade path executes.
7. The executor measures realized profit.
8. The loan principal and fee are repaid.
9. Profit is forwarded to the recipient.
10. Events are emitted for audit and settlement.

This path is atomic: if a validation step, repayment step, or router check fails, the whole transaction reverts.

## Signal Verification Details

The contract verification path mirrors the Python encoder exactly.

The contract reconstructs the hash from:

- `opportunityId`
- `dexA`
- `dexB`
- `borrowToken`
- `borrowAmount`
- `minProfit`
- `deadline`
- `chainId`

It then applies the Ethereum signed-message prefix and recovers the signer using ECDSA. This is the critical compatibility point with [compute/signal_encoder.py](../compute/signal_encoder.py).

## Flashloan Lifecycle Details

`LendingPool.flashLoan()` performs the following checks:

- token must be supported
- requested amount must fit within available liquidity
- callback must return the expected ERC-3156 hash
- post-callback balance must cover the borrowed amount plus fee

`ArbitrageExecutor.onFlashLoan()` then:

- validates the caller
- validates configuration
- checks router allowlisting
- executes the trade
- checks realized profit
- repays the pool
- sends profit onward

These steps give Flashix a clean borrow/execute/repay boundary that the settlement and monitoring layers can reason about.

## Configuration And Deployment Notes

The deployment artifacts under [contracts/](../contracts/) should be treated as the source of truth for the currently deployed network state.

Key points:

- Deployment manifests live under `contracts/deployments/`.
- TypeChain and ABI outputs are generated under `contracts/typechain-types/` and `contracts/abi/`.
- The Hardhat workspace must match the target chain configuration before any verification or replay testing.

Before deploying or re-running the contracts:

1. Confirm the trusted signer address.
2. Confirm the token addresses for the target chain.
3. Confirm the router allowlist.
4. Confirm the pool liquidity.
5. Confirm the expected chain ID.

## Operational And Security Properties

- Replay protection comes from `usedSignals` in `SignalValidator`.
- Execution safety comes from the flashloan callback and repayment checks.
- Router allowlisting prevents arbitrary DEX usage.
- The `Pausable` and `Ownable` inheritance in the execution contracts support emergency control and administrative updates.
- The execution receipt is emitted as an event, which keeps the proof trail auditable without requiring the UI to infer state from heuristics.

## What The UI Shows

The frontend surfaces this contract behavior in the execution and compute views:

- The Compute page shows the linked request, validation state, and proof artifact.
- The Execution page shows the on-chain proof card and explorer links.
- The Settlement page uses the execution outcome to summarize realized PnL and exports.

## Related Files

- [contracts/contracts/SignalValidator.sol](../contracts/contracts/SignalValidator.sol)
- [contracts/contracts/LendingPool.sol](../contracts/contracts/LendingPool.sol)
- [contracts/contracts/ArbitrageExecutor.sol](../contracts/contracts/ArbitrageExecutor.sol)
- [compute/attestation.py](../compute/attestation.py)
- [compute/signal_encoder.py](../compute/signal_encoder.py)
