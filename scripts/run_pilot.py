"""End-to-end pilot driver: 2 assets x {B0, B2, M} x 5 reps.

Usage:
  python scripts/run_pilot.py                 # uses frozen tasks
  python scripts/run_pilot.py --reps 5 --methods B0 B2 M
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.benchmark.runner import run_benchmark
from model2agent import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="+", default=["cnn_digits", "xgb_tabular"])
    ap.add_argument("--methods", nargs="+", default=["B0", "B2", "M"])
    ap.add_argument("--reps", type=int, default=config.REPS_PER_TASK)
    ap.add_argument("--tasks", default=str(ROOT / "results" / "frozen" / "tasks.json"))
    ap.add_argument("--log", default=str(config.LOGS_DIR / "pilot_runs.jsonl"))
    a = ap.parse_args()
    summary = run_benchmark(a.slugs, methods=tuple(a.methods), reps=a.reps,
                            tasks_path=a.tasks, log_path=a.log)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    with open(config.LOGS_DIR / "pilot_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
