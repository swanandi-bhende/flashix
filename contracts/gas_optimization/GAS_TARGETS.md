# GAS_TARGETS v1.0.0

This document is the source-of-truth for gas budgets used by Flashix's Hardhat gas reporter, on-chain executor, and agent-side pre-screening.

## Budgets

| Constant | Value | Meaning |
| --- | ---:| --- |
| `SINGLE_TRADE_GAS_TARGET` | `180000` | Hard ceiling per trade on mainnet |
| `BATCH_TRADE_GAS_TARGET_PER_TRADE` | `150000` | Target per trade when batching 2+ signals |
| `SIGNAL_VALIDATION_GAS_BUDGET` | `8000` | Budget for signature recovery and nonce check |
| `FLASHLOAN_OVERHEAD_GAS` | `25000` | Fixed flashloan initiation and repayment overhead |
| `DEX_ROUTING_GAS_PER_LEG` | `45000` | One perp open or close on a single DEX |
| `PROFIT_SETTLEMENT_GAS` | `12000` | Profit transfer plus event emission |
| `MEV_BURN_BASE_GAS` | `5000` | Coinbase transfer overhead for MEV burn |

## Batching Rules

- Buffer signals for up to 5 seconds.
- Flush at 2-5 signals, or earlier if the batch is full.
- Do not batch a single trade unless a window is already open and another signal arrives before timeout.
- Reject batches larger than 5 trades to preserve gas headroom on 0G Chain.

## Enforcement

- The Hardhat gas reporter must fail if a profiled execution exceeds the budget table above.
- The agent-side estimator must use the same constants as the Solidity interface in `contracts/interfaces/IGasConstants.sol`.
- Release artifacts should publish gas reports to `docs/gas_reports/` for reproducibility.

## Versioning

- `v1.0.0`: Initial batch execution architecture, MEV burn hooks, and shared gas constants.
