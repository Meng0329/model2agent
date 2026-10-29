"""Statistical analysis driver: descriptive stats, paired comparisons, cluster bootstrap CI.

Usage: python scripts/run_analysis.py [--log results/logs/pilot_runs.jsonl]
Writes results/csv/summary.csv and results/logs/analysis.json (no fabricated numbers).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.stats import load_records, descriptive_only, paired_compare, cluster_bootstrap_ci
from model2agent.benchmark.metrics import write_summary_csv, per_method_costs, capability_verification_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(ROOT / "results" / "logs" / "pilot_runs.jsonl"))
    a = ap.parse_args()
    recs = load_records(a.log)
    out = {
        "n_records": len(recs),
        "descriptive": descriptive_only(recs),
        "paired_M_vs_B0": paired_compare(recs, "M", "B0"),
        "paired_M_vs_B2": paired_compare(recs, "M", "B2"),
        "cluster_bootstrap_M_vs_B0": cluster_bootstrap_ci(recs, "M", "B0"),
        "cluster_bootstrap_M_vs_B2": cluster_bootstrap_ci(recs, "M", "B2"),
        "costs": per_method_costs(recs),
        "capability_verification": capability_verification_rate(recs),
    }
    (ROOT / "results" / "logs" / "analysis.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=float))
    write_summary_csv(recs, ROOT / "results" / "csv" / "summary.csv")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
