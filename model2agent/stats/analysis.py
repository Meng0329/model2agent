"""Statistical analysis (aligned to Paper2Agent: paired tests, bootstrap 95% CI, effect sizes).

- Per (method, model, split): aggregate accuracy from raw records.
- Paired comparisons: paired t-test / Wilcoxon on per-run accuracy between M and a baseline.
- Model-level cluster bootstrap: resample models (clusters), keep all reps within a resampled
  model, to get 95% CI of the accuracy *difference* that respects clustering.
- Do NOT conclude from a single p-value; report effect size + CI.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


def load_records(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _per_run_correct(records, rep_key=("slug", "task_id")):
    """Return {(method, model, split): [list of correct bools per rep]}."""
    out = defaultdict(list)
    for r in records:
        if r.get("record_type") != "task_run":
            continue
        key = (r["method"], r["slug"], r.get("split", "tutorial"))
        out[key].append(bool(r.get("correct")))
    return out


def paired_compare(records, method_a="M", method_b="B0"):
    """Paired per-(model, task) accuracy between two methods. Returns stats dict."""
    by_task = defaultdict(dict)
    for r in records:
        if r.get("record_type") != "task_run":
            continue
        by_task[(r["slug"], r["task_id"])][r["method"]] = bool(r.get("correct"))
    pairs_a, pairs_b = [], []
    for k, d in by_task.items():
        if method_a in d and method_b in d:
            pairs_a.append(d[method_a]); pairs_b.append(d[method_b])
    pairs_a, pairs_b = np.array(pairs_a, dtype=float), np.array(pairs_b, dtype=float)
    if len(pairs_a) < 2:
        return {"n_pairs": len(pairs_a), "note": "insufficient pairs"}
    diff = pairs_a - pairs_b
    t_stat, p_t = stats.ttest_rel(pairs_a, pairs_b)
    try:
        w_stat, p_w = stats.wilcoxon(pairs_a, pairs_b)
    except ValueError:
        w_stat, p_w = float("nan"), float("nan")
    sd = diff.std(ddof=1) if len(diff) > 1 else float("nan")
    dz = (diff.mean() / sd) if sd and not np.isnan(sd) else float("nan")
    return {
        "n_pairs": len(pairs_a),
        "acc_a": float(pairs_a.mean()), "acc_b": float(pairs_b.mean()),
        "mean_diff": float(diff.mean()),
        "paired_t": float(t_stat), "p_t": float(p_t),
        "wilcoxon_p": float(p_w), "cohen_dz": float(dz),
    }


def cluster_bootstrap_ci(records, method_a="M", method_b="B0", n_boot=10000, seed=20261029):
    """Model-level clustered bootstrap of the accuracy-difference 95% CI."""
    rng = np.random.default_rng(seed)
    by_model = defaultdict(lambda: defaultdict(dict))  # model -> {task_id: {method: correct}}
    for r in records:
        if r.get("record_type") != "task_run":
            continue
        by_model[r["slug"]][r["task_id"]][r["method"]] = bool(r.get("correct"))
    models = list(by_model.keys())
    if not models:
        return {"error": "no data"}
    diffs = []
    for _ in range(n_boot):
        sel = rng.choice(models, size=len(models), replace=True)
        a, b = [], []
        for m in sel:
            for task_id, md in by_model[m].items():
                if method_a in md and method_b in md:
                    a.append(md[method_a]); b.append(md[method_b])
        if a:
            diffs.append(np.mean(a) - np.mean(b))
    diffs = np.array(diffs)
    return {
        "diff_mean": float(np.mean(diffs)),
        "ci_low": float(np.percentile(diffs, 2.5)),
        "ci_high": float(np.percentile(diffs, 97.5)),
        "n_boot": n_boot, "n_models": len(models),
    }


def descriptive_only(records):
    """For the 2-model pilot: report only descriptive stats (no cross-model generalization claim)."""
    agg = _per_run_correct(records)
    out = {}
    for (method, model, split), vals in agg.items():
        out.setdefault(method, {}).setdefault(model, {})[split] = {
            "n": len(vals), "accuracy": float(np.mean(vals)) if vals else 0.0}
    return {"descriptive": out, "note": "2-model pilot: descriptive only; no cross-model generalization claimed"}
