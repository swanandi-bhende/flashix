"""
Training script for arbitrage scorer.

This script builds a deterministic GradientBoostingClassifier on synthetic data
when live data isn't available. It writes:
- models/arbitrage_scorer_v1.pkl
- models/arbitrage_scorer_v1_metadata.json

Run this outside the enclave. The TEE will load and validate the produced files.
"""
from __future__ import annotations

import os
import json
from datetime import datetime
import hashlib
import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score


def generate_synthetic_dataset(n_samples=6000, random_state=42):
    rng = np.random.default_rng(random_state)
    X = rng.normal(size=(n_samples, 12))
    # create a label that favors larger spread and positive funding diff
    spreads = np.abs(X[:, 0])
    funding_diff = X[:, 1]
    borrow_log = X[:, 2]
    score = 2.0 * spreads + 0.5 * funding_diff + 0.3 * borrow_log + rng.normal(scale=0.5, size=n_samples)
    y = (score > np.quantile(score, 0.6)).astype(int)
    return X, y


def main():
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "models")
    models_dir = os.path.abspath(models_dir)
    os.makedirs(models_dir, exist_ok=True)

    X, y = generate_synthetic_dataset()
    X_train, X_rest, y_train, y_rest = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_rest, y_rest, test_size=0.3333, random_state=42, stratify=y_rest)

    param_grid = {
        "n_estimators": [50, 100],
        "max_depth": [3, 5],
        "learning_rate": [0.1, 0.05],
    }
    gbc = GradientBoostingClassifier(random_state=42)
    gs = GridSearchCV(gbc, param_grid, scoring="f1", cv=3, n_jobs=1)
    gs.fit(X_train, y_train)

    best = gs.best_estimator_
    preds = best.predict(X_val)
    val_f1 = f1_score(y_val, preds)
    val_prec = precision_score(y_val, preds)
    val_rec = recall_score(y_val, preds)

    model_fname = os.path.join(models_dir, "arbitrage_scorer_v1.pkl")
    joblib.dump(best, model_fname)

    # compute sha256
    with open(model_fname, "rb") as fh:
        h = hashlib.sha256(fh.read()).hexdigest()

    metadata = {
        "version": "v1",
        "sha256": h,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "feature_names": [
            "gross_spread_percent",
            "funding_rate_diff",
            "borrow_amount_log",
            "orderbook_depth_ratio",
            "trade_flow_imbalance_diff",
            "volatility_24h",
            "correlation_btc",
            "time_of_day_sin",
            "time_of_day_cos",
            "day_of_week",
            "gas_price_gwei",
            "spread_momentum_5s",
        ],
        "validation_f1": float(val_f1),
        "validation_precision": float(val_prec),
        "validation_recall": float(val_rec),
        "training_samples": int(len(X_train)),
    }
    meta_fname = os.path.join(models_dir, "arbitrage_scorer_v1_metadata.json")
    with open(meta_fname, "w") as fh:
        json.dump(metadata, fh, indent=2)

    print("Wrote model:", model_fname)
    print("Wrote metadata:", meta_fname)


if __name__ == "__main__":
    main()
