"""Metrics aligned to the Paper2Agent evidence chain, computed from raw JSONL records."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path


def load_records(path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def aggregate_task_accuracy(records: list[dict]) -> dict:
    """Per (method, slug, split): accuracy over all reps."""
    bucket = defaultdict(list)
    for r in records:
        if r.get("record_type") != "task_run":
            continue
        bucket[(r["method"], r["slug"], r["split"])].append(bool(r.get("correct")))
    out = {}
    for (m, s, sp), vals in bucket.items():
        out.setdefault(m, {}).setdefault(s, {})[sp] = {
            "n": len(vals), "accuracy": sum(vals) / len(vals) if vals else 0.0,
        }
    return out


def capability_verification_rate(records: list[dict]) -> dict:
    """Per method: fraction of capability-execution checks that matched reference."""
    bucket = defaultdict(list)
    for r in records:
        if r.get("record_type") != "capability_verify":
            continue
        bucket[r["method"]].append(bool(r.get("correct")))
    return {m: {"n": len(v), "rate": sum(v) / len(v) if v else 0.0} for m, v in bucket.items()}


def per_method_costs(records: list[dict]) -> dict:
    """Cost/latency summaries per method (from task_run + capability_verify)."""
    agg = defaultdict(lambda: {"llm_cost_usd": 0.0, "latency_ms": 0.0, "n": 0, "errors": 0})
    for r in records:
        if r.get("record_type") not in ("task_run", "capability_verify"):
            continue
        a = agg[r["method"]]
        a["llm_cost_usd"] += float(r.get("llm_cost_usd", 0.0))
        a["latency_ms"] += float(r.get("latency_ms", 0.0))
        a["n"] += 1
        a["errors"] += 0 if r.get("ok", True) else 1
    for m, a in agg.items():
        a["avg_latency_ms"] = a["latency_ms"] / a["n"] if a["n"] else 0.0
        a["avg_cost_usd"] = a["llm_cost_usd"] / a["n"] if a["n"] else 0.0
    return dict(agg)


def write_summary_csv(records: list[dict], path) -> None:
    import pandas as pd
    acc = aggregate_task_accuracy(records)
    rows = []
    for m, per_slug in acc.items():
        for s, per_split in per_slug.items():
            for sp, d in per_split.items():
                rows.append({"method": m, "model": s, "split": sp, "n": d["n"], "accuracy": d["accuracy"]})
    pd.DataFrame(rows).to_csv(path, index=False)
