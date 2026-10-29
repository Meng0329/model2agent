"""Robustness driver: inject faults into both pilots and report detection/repair/consistency.

Usage: python scripts/run_robustness.py [--slugs cnn_digits xgb_tabular]
Writes results/logs/fault_results_<slug>.json.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.robustness.fault_injection import run_fault_injection, save_fault_results, FAULT_TYPES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="+", default=["cnn_digits", "xgb_tabular"])
    a = ap.parse_args()
    for slug in a.slugs:
        print(f"=== fault injection: {slug} ===")
        results = run_fault_injection(slug, methods=("M",), faults=FAULT_TYPES, repair=True)
        path = ROOT / "results" / "logs" / f"fault_results_{slug}.json"
        save_fault_results(slug, results, path)
        for r in results:
            print(f"  {r.fault:24s} detected={r.detected} repaired={r.repaired} "
                  f"consistent={r.post_repair_consistent} unsafe_rejected={r.unsafe_rejected}")
        print(f"  -> {path}")


if __name__ == "__main__":
    main()
