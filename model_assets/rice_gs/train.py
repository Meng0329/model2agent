"""Train a rice genomic-selection model (real genotypes, real measured trait).

Protocol:
* Lines with a non-missing target trait are kept.
* SNPs are pruned by variance computed ONLY on the training split (no test leakage).
* alpha is selected by K-fold CV inside the training split only.
* The held-out candidate pool is never used for tuning; its measured trait values are
  written to the hidden oracle, not to the model asset.

Outputs (inside this asset): model.json, genotypes_pruned.npz, split.json, metrics.json.
The hidden oracle is written by scripts/build_scientist_benchmark.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "m2a_data" / "research" / "datasets" / "rice"
TRAIT = "GRWT100"
N_SNPS = 2000
SEED = 20261029


def main() -> None:
    geno = pd.read_csv(DATA / "genotypes.csv", index_col=0)
    traits = pd.read_csv(DATA / "traits.csv", index_col=0)
    ids = [i for i in geno.index if i in traits.index and pd.notna(traits.loc[i, TRAIT])]
    ids.sort()
    X = geno.loc[ids].astype(float)
    y = traits.loc[ids, TRAIT].astype(float).values

    rng = np.random.RandomState(SEED)
    perm = rng.permutation(len(ids))
    n_train = int(0.6 * len(ids))
    train_idx, pool_idx = np.sort(perm[:n_train]), np.sort(perm[n_train:])

    # variance pruning on TRAIN ONLY
    var = X.iloc[train_idx].var(axis=0).sort_values(ascending=False)
    snps = list(var.index[:N_SNPS])
    Xp = X[snps].values.astype(np.float32)

    scaler = StandardScaler().fit(Xp[train_idx])
    Xtr = scaler.transform(Xp[train_idx])

    best_alpha, best_rho = None, -9.0
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    for alpha in (1.0, 10.0, 100.0, 1000.0):
        rhos = []
        for a, b in kf.split(Xtr):
            m = Ridge(alpha=alpha).fit(Xtr[a], y[train_idx][a])
            rhos.append(spearmanr(m.predict(Xtr[b]), y[train_idx][b]).correlation)
        rho = float(np.mean(rhos))
        if rho > best_rho:
            best_alpha, best_rho = alpha, rho

    model = Ridge(alpha=best_alpha).fit(Xtr, y[train_idx])
    pred_pool = model.predict(scaler.transform(Xp[pool_idx]))
    heldout_rho = float(spearmanr(pred_pool, y[pool_idx]).correlation)
    top = np.argsort(-pred_pool)[:20]
    quartile = float(np.quantile(y[pool_idx], 0.75))
    top_hit = float(np.mean(y[pool_idx][top] >= quartile))

    (HERE / "model.json").write_text(json.dumps({
        "trait": TRAIT,
        "alpha": best_alpha,
        "cv_spearman_train": round(best_rho, 4),
        "feature_names": snps,
        "coef": [float(c) for c in model.coef_],
        "intercept": float(model.intercept_),
        "scaler_mean": [float(v) for v in scaler.mean_],
        "scaler_scale": [float(v) for v in scaler.scale_],
        "train_ids": [ids[i] for i in train_idx],
        "pool_ids": [ids[i] for i in pool_idx],
        "source": "Orhobor et al. 2018, doi:10.17632/sr8zzsrpcs.1 (CC-BY-SA-4.0)",
    }, ensure_ascii=False, indent=2))
    np.savez_compressed(HERE / "genotypes_pruned.npz", ids=np.array(ids),
                        snps=np.array(snps), X=Xp)
    (HERE / "split.json").write_text(json.dumps({
        "trait": TRAIT,
        "train_ids": [ids[i] for i in train_idx],
        "pool_ids": [ids[i] for i in pool_idx],
        "n_train": len(train_idx), "n_pool": len(pool_idx),
    }, ensure_ascii=False, indent=2))
    (HERE / "metrics.json").write_text(json.dumps({
        "trait": TRAIT, "model": "Ridge", "alpha": best_alpha,
        "cv_spearman_train": round(best_rho, 4),
        "heldout_spearman_pool": round(heldout_rho, 4),
        "heldout_top20_quartile_hit": round(top_hit, 4),
        "n_lines": len(ids), "n_snps": N_SNPS, "seed": SEED,
    }, ensure_ascii=False, indent=2))
    print(json.dumps(json.loads((HERE / "metrics.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
