# Inference Module — Model Card & Verifiable Computation

## Model Card

- **Model type:** Gradient Boosted Classifier
- **Versioning:** Each model release is saved as `models/arbitrage_scorer_{version}.pkl` with a paired metadata JSON containing SHA-256 checksum and training metadata.
- **Training data:** 30 days of historical perpetual-swap pricing (Hyperliquid, dYdX), N samples (or synthetic dataset for local tests). Training script: `compute/model_training/train_arbitrage_scorer.py`.
- **Input features (12):** gross_spread_percent, funding_rate_diff, borrow_amount_log, orderbook_depth_ratio, trade_flow_imbalance_diff, volatility_24h, correlation_btc, time_of_day_sin, time_of_day_cos, day_of_week, gas_price_gwei, spread_momentum_5s
- **Output interpretation:** `confidence` is model-estimated P(PROFITABLE). `risk_score = 1 - confidence`. Decision threshold: execute if `confidence>0.75 and risk_score<0.6 and expected_profit > MIN_PROFIT_USDC`.
- **Known limitations:** Trained on specific DEX data. Performance on different liquidity regimes may differ.
- **Performance:** See `models/arbitrage_scorer_v1_metadata.json` for validation F1, precision, recall.

## Verifiable Computation Proof

How a judge can validate sealed inference:

1. Clone the repo.
2. Run the training script to generate the pinned model:

```bash
python compute/model_training/train_arbitrage_scorer.py
```

3. Verify model checksum:

```bash
python -c "from compute.model_loader import ModelLoader; ModelLoader('models').load()"
```

4. Run determinism tests:

```bash
pytest tests/unit/compute/test_determinism.py -q
```

5. Re-run `analyze()` on any logged input and compare the `output_hash` and `tee_signature` — they must match the archived log entry.

## Determinism Guarantees

- Fixed random seeds in training and synthetic dataset generation.
- Float64 used explicitly for all NumPy arrays.
- Monetary arithmetic performed with `Decimal`.
- All JSON serializations use `sort_keys=True`.
- Model pinned by SHA-256 and verified at TEE startup.
- Feature transformations are deterministic and clamp values to prevent NaN/Inf.

## Data Flow

```mermaid
flowchart LR
  A[InferenceInput] --> B[FeatureExtractor]\n  B --> C[InferenceEngine]\n+  C --> D[SignalBuilder]\n+  D --> E[TEESigner]\n+  E --> F[InferenceOutput]
```
