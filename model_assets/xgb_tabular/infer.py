"""Native inference entry for the xgb-breast-cancer asset (part of the model asset, NOT agent code)."""
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
import json
from pathlib import Path
import numpy as np
import xgboost as xgb

_HERE = Path(__file__).resolve().parent
_cache = {}

def _load():
    if "model" not in _cache:
        m = xgb.XGBClassifier()
        m.load_model(str(_HERE / "model.json"))
        feat = json.loads((_HERE / "metrics.json").read_text())["feature_names"]
        _cache.update(model=m, feature_names=feat)
    return _cache["model"], _cache["feature_names"]

def predict(features: list) -> int:
    """Predict class (0=malignant, 1=benign) for a 30-dim feature vector (breast_cancer schema)."""
    m, _ = _load()
    arr = np.asarray(features, dtype=np.float32).reshape(1, -1)
    return int(m.predict(arr)[0])

def predict_proba(features: list) -> dict:
    """Return class -> probability for a 30-dim input."""
    m, _ = _load()
    arr = np.asarray(features, dtype=np.float32).reshape(1, -1)
    probs = m.predict_proba(arr)[0]
    return {str(int(c)): float(p) for c, p in zip(m.classes_, probs)}

def explain(top_k: int = 8) -> list:
    """Return the top-k most important features by XGBoost gain importance."""
    m, feat = _load()
    gain = m.get_booster().get_score(importance_type="gain")
    # map f0..fN -> human feature names where possible
    rows = []
    for k, v in sorted(gain.items(), key=lambda kv: kv[1], reverse=True)[:top_k]:
        idx = int(k[1:]) if k.startswith("f") and k[1:].isdigit() else None
        name = feat[idx] if idx is not None and idx < len(feat) else k
        rows.append({"feature": name, "gain": float(v)})
    return rows

def classes() -> list:
    """Return the list of class labels the model was trained on."""
    m, _ = _load()
    return [int(c) for c in m.classes_]
