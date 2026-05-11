import os
import json
import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple

import joblib
import numpy as np

_logger = logging.getLogger(__name__)


class ModelIntegrityError(Exception):
    def __init__(self, expected: str, actual: str):
        super().__init__(f"Model checksum mismatch: expected={expected} actual={actual}")
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class ModelMetadata:
    version: str
    sha256_checksum: str
    trained_at: str
    feature_names: list
    training_sample_size: int
    validation_accuracy: float


class ModelLoader:
    FIXED_TEST_VECTOR = np.zeros(12, dtype=np.float64)

    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.model_version = os.environ.get("MODEL_VERSION", "v1")

    def _paths(self):
        base = f"arbitrage_scorer_{self.model_version}"
        pkl = os.path.join(self.model_dir, f"{base}.pkl")
        meta = os.path.join(self.model_dir, f"{base}_metadata.json")
        return pkl, meta

    def load(self) -> Tuple[object, ModelMetadata]:
        pkl_path, meta_path = self._paths()
        if not os.path.exists(pkl_path) or not os.path.exists(meta_path):
            raise FileNotFoundError(f"Model files not found: {pkl_path}, {meta_path}")

        with open(meta_path, "r") as fh:
            meta_raw = json.load(fh)

        metadata = ModelMetadata(
            version=meta_raw["version"],
            sha256_checksum=meta_raw["sha256"],
            trained_at=meta_raw.get("trained_at", ""),
            feature_names=meta_raw.get("feature_names", []),
            training_sample_size=int(meta_raw.get("training_samples", 0)),
            validation_accuracy=float(meta_raw.get("validation_f1", 0.0)),
        )

        # checksum BEFORE loading model
        with open(pkl_path, "rb") as fh:
            data = fh.read()
        actual = hashlib.sha256(data).hexdigest()
        expected = metadata.sha256_checksum
        if actual != expected:
            raise ModelIntegrityError(expected, actual)

        # load model
        model = joblib.load(pkl_path)

        # determinism smoke test
        out1 = model.predict_proba(self.FIXED_TEST_VECTOR.reshape(1, -1))
        out2 = model.predict_proba(self.FIXED_TEST_VECTOR.reshape(1, -1))
        if not (out1.shape == out2.shape and (out1 == out2).all()):
            raise RuntimeError("Model predict_proba not deterministic in smoke test")

        _logger.info(f"MODEL_LOADED: version={metadata.version}, sha256={actual[:8]}...")

        return model, metadata


# Load exactly once at module import and export as singleton
_default_dir = os.environ.get("MODEL_DIR", "models")
try:
    MODEL_SINGLETON = ModelLoader(_default_dir).load()
except Exception:
    # propagate error so startup fails loudly if model invalid
    raise
