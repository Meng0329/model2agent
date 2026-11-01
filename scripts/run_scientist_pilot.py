"""Run Model2ScientistBench (S1/S2) with real SDK agents and score against hidden oracles.

Every run is immutable: a unique run_id, a raw run record, and the agent artifacts.
Failures are recorded as FAILED — never converted into successes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent import config  # noqa: E402
from model2agent.orchestrator import run_smsc  # noqa: E402
from model2agent.scientist.evidence import RunLedger, new_run_id  # noqa: E402
from model2agent.scientist.methods import run_baseline  # noqa: E402
from model2agent.scientist.runner import (  # noqa: E402
    evaluate_task, make_run_record, run_scientist_project,
)

BUNDLES = {"esm2_variant": ROOT / "model_assets" / "esm2_variant",
           "rice_gs": ROOT / "model_assets" / "rice_gs"}
TASKS = ROOT / "results" / "frozen" / "scientist_tasks.json"
HIDDEN = ROOT / "m2a_data" / "research" / "hidden"
PROJECTS = ROOT / "m2a_data" / "research" / "scientists"
LOG = ROOT / "results" / "logs" / "scientist_runs.jsonl"


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _ensure_project(task: dict, timeout_turns: int, budget: float) -> tuple[Path, str]:
    bundle = BUNDLES[task["scientific_model"]]
    project = PROJECTS / task["scientific_model"]
    if (project / "config.json").exists() and (project / "scientist.json").exists():
        return project, "OBSERVED"
    res = run_smsc(bundle, task, project_dir=project,
                   max_turns=timeout_turns, max_budget_usd=budget)
    status = "OBSERVED" if res.get("success") else "FAILED"
    return project, status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="S1")
    ap.add_argument("--methods", nargs="+", default=["B0", "B1", "B2", "B3", "M"])
    ap.add_argument("--tasks", nargs="+", default=None)
    ap.add_argument("--domains", nargs="+", default=None)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--gen-turns", type=int, default=50)
    ap.add_argument("--gen-budget", type=float, default=4.0)
    args = ap.parse_args()

    config.assert_secrets()
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    if args.tasks:
        tasks = [t for t in tasks if t["task_id"] in set(args.tasks)]
    if args.domains:
        tasks = [t for t in tasks if t["domain"] in set(args.domains)]

    ledger = RunLedger(LOG)
    commit = _commit()
    rows = []
    for task in tasks:
        for method in args.methods:
            gen_status = "OBSERVED"
            project = None
            if method == "M":
                project, gen_status = _ensure_project(task, args.gen_turns, args.gen_budget)
                if gen_status != "OBSERVED":
                    rows.append({"task": task["task_id"], "method": method,
                                 "status": "FAILED", "reason": "agent generation failed"})
                    print(f"[FAILED] {task['task_id']} {method}: agent generation failed")
                    continue
            for rep in range(args.reps):
                run_id = new_run_id(args.stage, method, task["task_id"], rep)
                out = (ROOT / "results" / "experiments" / args.stage /
                       task["task_id"] / method / f"rep{rep}")
                t0 = time.perf_counter()
                try:
                    if method == "M":
                        run_scientist_project(project, task, run_id, out, HIDDEN)
                    else:
                        run_baseline(method, task, BUNDLES[task["scientific_model"]],
                                     out, HIDDEN, run_id)
                    ev = evaluate_task(task, out, HIDDEN)
                except Exception as e:
                    ev = {"oracle_ok": False, "sisr_success": False, "detail": {},
                          "model_calls": 0, "oracle_queries": 0, "evidence_records": 0,
                          "malformed_evidence": 0, "revisions": 0, "artifacts_ok": False,
                          "sev": {"evidence_validity": 0.0, "unsupported_claim_rate": 0.0},
                          "status": "FAILED", "cost_usd": 0.0,
                          "latency_s": round(time.perf_counter() - t0, 2),
                          "out_dir": str(out), "error": f"{type(e).__name__}: {e}"}
                rec = make_run_record(task, method, run_id, rep, ev, stage=args.stage,
                                      agent_generation_status=gen_status,
                                      builder_commit=commit)
                ledger.append(rec)
                rows.append({"task": task["task_id"], "method": method, "run_id": run_id,
                             "status": ev.get("status"), "sisr": ev["sisr_success"],
                             "oracle_ok": ev["oracle_ok"], "model_calls": ev["model_calls"],
                             "oracle_queries": ev["oracle_queries"],
                             "evidence": ev["evidence_records"],
                             "malformed": ev.get("malformed_evidence", 0),
                             "sev": ev["sev"]["evidence_validity"],
                             "cost": ev["cost_usd"], "latency": ev["latency_s"],
                             "error": ev.get("error")})
                print(f"[{args.stage}] {task['task_id']} {method} rep{rep}: "
                      f"sisr={ev['sisr_success']} oracle={ev['oracle_ok']} "
                      f"calls={ev['model_calls']} ev={ev['evidence_records']} "
                      f"cost=${ev['cost_usd']:.3f}")
    (ROOT / "results" / "logs" / f"scientist_{args.stage}_runs_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
