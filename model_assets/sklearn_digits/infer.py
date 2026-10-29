"""Native inference entry for the digits-rf asset (part of the model asset, NOT agent code)."""
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
import json
from pathlib import Path
import joblib

_HERE = Path(__file__).resolve().parent
_bundle = None

def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(_HERE / "model.joblib")
    return _bundle

def predict(features: list) -> int:
    """Predict the digit class (0-9) for a 64-dim pixel-flattened input (values 0..16)."""
    b = _load()
    import numpy as np
    arr = np.asarray(features, dtype=float).reshape(1, -1)
    return int(b["model"].predict(arr)[0])

def predict_proba(features: list) -> dict:
    """Return class -> probability for a 64-dim input."""
    b = _load()
    import numpy as np
    arr = np.asarray(features, dtype=float).reshape(1, -1)
    probs = b["model"].predict_proba(arr)[0]
    return {str(c): float(p) for c, p in zip(b["model"].classes_, probs)}

def explain(top_k: int = 10) -> list:
    """Return the top-k most important pixel features (Gini importance)."""
    b = _load()
    import numpy as np
    fi = b["model"].feature_importances_
    idx = np.argsort(fi)[::-1][:top_k]
    return [{"feature": b["feature_names"][int(i)], "importance": float(fi[int(i)])} for i in idx]

def classes() -> list:
    """Return the list of class labels the model was trained on."""
    b = _load()
    return list(b["classes"])
