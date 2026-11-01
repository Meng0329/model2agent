"""Rice genomic-selection model (Ridge on pruned SNP dosages).

Real trained weights only. Predictions are MODEL PREDICTIONS (E1); they are not
measured phenotypes and must never be reported as such.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_MODEL = json.loads((HERE / "model.json").read_text(encoding="utf-8"))

_coef = np.array(_MODEL["coef"], dtype=np.float64)
_intercept = float(_MODEL["intercept"])
_mean = np.array(_MODEL["scaler_mean"], dtype=np.float64)
_scale = np.array(_MODEL["scaler_scale"], dtype=np.float64)
_snps = list(_MODEL["feature_names"])


@functools.lru_cache(maxsize=1)
def _genotypes():
    z = np.load(HERE / "genotypes_pruned.npz", allow_pickle=False)
    ids = [str(x) for x in z["ids"]]
    return {gid: i for i, gid in enumerate(ids)}, z["X"]


def _predict_matrix(X: np.ndarray) -> np.ndarray:
    if X.ndim == 1:
        X = X[None, :]
    if X.shape[1] != len(_coef):
        raise ValueError(f"expected {len(_coef)} SNP features, got {X.shape[1]}")
    Z = (X - _mean) / _scale
    return Z @ _coef + _intercept


def predict_phenotype(genotype: list[float]) -> float:
    """Predicted trait value for one genotype vector (pruned SNP order)."""
    return float(_predict_matrix(np.asarray(genotype, dtype=np.float64))[0])


def predict_by_ids(ids: list[str]) -> list[dict]:
    """Predict trait values for named rice lines (real genotype lookup)."""
    index, X = _genotypes()
    missing = [i for i in ids if i not in index]
    if missing:
        raise KeyError(f"unknown line ids: {missing[:5]}")
    rows = np.stack([X[index[i]] for i in ids]).astype(np.float64)
    preds = _predict_matrix(rows)
    return [{"id": i, "predicted": float(p)} for i, p in zip(ids, preds)]


def rank_candidates(ids: list[str]) -> list[dict]:
    """Rank candidate lines by predicted trait value (descending)."""
    scored = predict_by_ids(ids)
    return sorted(scored, key=lambda r: -r["predicted"])


def feature_importance(top_k: int = 8) -> list[dict]:
    """Largest standardized Ridge coefficients (association, not causation)."""
    order = np.argsort(-np.abs(_coef))[:top_k]
    return [{"snp": _snps[i], "coef": float(_coef[i])} for i in order]


def trait() -> str:
    return str(_MODEL["trait"])
