"""S2 ablations — real, scored, and honest.

Two compiler ablations (same task, same runtime, same budget, same oracle):
  A9-single   : the outer Model2Agent compiler runs with NO subagents (single agent).
  A1-no-graph : the compiler has no affordance-analyst and no capability-graph-builder.

Each ablation generates a REAL scientist project with the reduced compiler, runs it
on the task via the shared runner, and scores it with the shared hidden oracle.
Results go to a SEPARATE ledger so the S1 grid is never contaminated.

Plus a contradiction-response audit over existing S1 M runs: it detects real
E1-prediction vs E3-measurement contradictions already present in the ledger and
checks whether a revision followed. It is observational (not a controlled
injection) and is labelled as such; it never fabricates a measurement.

Usage:
  python3 scripts/run_scientist_ablations.py --ablation A9-single --tasks rice-R2-closed-loop
  python3 scripts/run_scientist_ablations.py --ablation A1-no-graph --tasks rice-R2-closed-loop
  python3 scripts/run_scientist_ablations.py --contradiction-audit
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent import config  # noqa: E402
from model2agent.orchestrator import run_smsc  # noqa: E402
from model2agent.scientist.evidence import new_run_id  # noqa: E402
from model2agent.scientist.runner import (  # noqa: E402
    evaluate_task, run_scientist_project,
)
from model2agent.scientist.subagents import (  # noqa: E402
    AFFORDANCE_ANALYST, BUILDER_AGENTS, CAPABILITY_GRAPH_BUILDER,
    MODEL_PROFILER, SCIENTIST_SYNTHESIZER, VERIFICATION_AUDITOR,
)

BUNDLES = {"esm2_variant": ROOT / "model_assets" / "esm2_variant",
           "rice_gs": ROOT / "model_assets" / "rice_gs"}
TASKS = ROOT / "results" / "frozen" / "scientist_tasks.json"
HIDDEN = ROOT / "m2a_data" / "research" / "hidden"
ABL_DIR = ROOT / "m2a_data" / "research" / "ablations"
S1_LOG = ROOT / "results" / "logs" / "scientist_runs.jsonl"
LOG = ROOT / "results" / "logs" / "scientist_ablations.jsonl"

# A9: no subagents at all. A1: subagents minus affordance-analyst + capability-graph-builder.
ABLATIONS = {
    "A9-single": {
        "desc": "single outer agent (no subagents)",
        "agents": {},
    },
    "A1-no-graph": {
        "desc": "no affordance-analyst / no capability-graph-builder",
        "agents": {
            "model-profiler": MODEL_PROFILER,
            "scientist-synthesizer": SCIENTIST_SYNTHESIZER,
            "verification-auditor": VERIFICATION_AUDITOR,
        },
    },
}


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _s1_m_baseline(task_id: str) -> dict | None:
    """The matching S1 M run (most recent non-harness) for honest comparison."""
    best = None
    if not S1_LOG.exists():
        return None
    for line in S1_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (r.get("scientific_task_id") == task_id and r.get("method_id") == "M"
                and not str(r.get("failure_category") or "").startswith("harness_")):
            best = r
    return best


def _append(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_ablation(ablation: str, task: dict, gen_turns: int, gen_budget: float) -> dict:
    cfg = ABLATIONS[ablation]
    model = task["scientific_model"]
    project = ABL_DIR / ablation / model
    run_id = new_run_id("S2", ablation, task["task_id"], 0)

    # 1) real compilation with the reduced compiler
    t_gen = time.perf_counter()
    gen = run_smsc(BUNDLES[model], task, project_dir=project,
                   max_turns=gen_turns, max_budget_usd=gen_budget,
                   agents=cfg["agents"], ablation=ablation)
    gen_latency = round(time.perf_counter() - t_gen, 2)
    gen_status = "OBSERVED" if gen.get("success") else "FAILED"

    out = ROOT / "results" / "experiments" / "S2" / task["task_id"] / ablation / "rep0"
    ev: dict
    if gen_status != "OBSERVED":
        ev = {"oracle_ok": False, "sisr_success": False, "detail": {},
              "model_calls": 0, "oracle_queries": 0, "evidence_records": 0,
              "malformed_evidence": 0, "revisions": 0, "artifacts_ok": False,
              "sev": {"evidence_validity": 0.0, "unsupported_claim_rate": 0.0},
              "status": "FAILED", "cost_usd": 0.0,
              "latency_s": 0.0, "out_dir": str(out),
              "error": "compilation failed: " + "; ".join(gen.get("problems") or [])}
    else:
        # 2) real execution of the generated project against the hidden oracle
        try:
            run_scientist_project(project, task, run_id, out, HIDDEN)
            ev = evaluate_task(task, out, HIDDEN)
        except Exception as e:
            ev = {"oracle_ok": False, "sisr_success": False, "detail": {},
                  "model_calls": 0, "oracle_queries": 0, "evidence_records": 0,
                  "malformed_evidence": 0, "revisions": 0, "artifacts_ok": False,
                  "sev": {"evidence_validity": 0.0, "unsupported_claim_rate": 0.0},
                  "status": "FAILED", "cost_usd": 0.0,
                  "latency_s": 0.0, "out_dir": str(out),
                  "error": f"{type(e).__name__}: {e}"}

    base = _s1_m_baseline(task["task_id"]) or {}
    rec = {
        "stage": "S2", "ablation": ablation, "ablation_desc": cfg["desc"],
        "task_id": task["task_id"], "domain": task["domain"],
        "run_id": run_id, "builder_commit": _commit(),
        "generation_status": gen_status,
        "generation_cost_usd": float((gen.get("session") or {}).get("cost_usd", 0.0)),
        "generation_latency_s": gen_latency,
        "sisr": bool(ev["sisr_success"]), "oracle_ok": bool(ev["oracle_ok"]),
        "sev": float(ev["sev"]["evidence_validity"]),
        "revisions": int(ev.get("revisions", 0)),
        "model_calls": int(ev["model_calls"]),
        "oracle_queries": int(ev["oracle_queries"]),
        "cost_usd": float(ev.get("cost_usd", 0.0)),
        "latency_s": float(ev.get("latency_s", 0.0)),
        "error": ev.get("error"),
        "project_dir": str(project), "out_dir": str(out),
        "s1_m_baseline": {
            "run_id": base.get("run_id"),
            "sisr": bool(base.get("scientific_task_success")),
            "oracle_ok": bool(base.get("final_conclusion_validity")),
            "revisions": None,  # revisions are not a RunRecord field
            "model_calls": base.get("model_call_count"),
            "cost_usd": base.get("cost"),
        } if base else None,
    }
    _append(rec)
    return rec


# ---------------------------------------------------------------- contradiction audit

# Known candidate-id shapes in the two pilot domains. We only parse these, so a
# stray number in prose is never mistaken for a candidate.
_RICE_ID = re.compile(r"IRIS_313\.(\d{3,5})")
_RICE_SHORT = re.compile(r"(?<![\d.])(\d{4,5})(?=\s*[=: ])")
_PROT_ID = re.compile(r"\b([A-Z]\d{1,3}[A-Z])\b")


def _norm_id(raw: str) -> str:
    """Normalise rice ids so `IRIS_313.12254` and `12254` compare equal."""
    m = _RICE_ID.fullmatch(raw)
    if m:
        return m.group(1)
    return raw


def _pairs_from_record(rec: dict) -> dict[str, float]:
    """Extract (candidate_id -> numeric value) from one heterogeneous evidence record."""
    pairs: dict[str, float] = {}
    # 1) structured candidate_id + a numeric field
    cid = rec.get("candidate_id") or rec.get("candidate") or rec.get("input_id")
    if cid:
        for k in ("score", "predicted", "value", "measured", "fitness",
                  "measured_fitness", "observed", "result", "measurement"):
            v = rec.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                pairs[_norm_id(str(cid))] = float(v)
                break
    # 2) nested {id: number} result dicts anywhere in the record
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    ks = str(k)
                    if _RICE_ID.fullmatch(ks) or _PROT_ID.fullmatch(ks):
                        pairs.setdefault(_norm_id(ks), float(v))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(rec)
    # 3) free-text "ID=value" / "ID value" / "ID: value" inside string fields
    for k, v in rec.items():
        if not isinstance(v, str):
            continue
        for m in _RICE_ID.finditer(v):
            tail = v[m.end():m.end() + 12]
            mm = re.match(r"\s*(?:[=:]\s*)?([+-]?\d+(?:\.\d+)?)", tail)
            if mm:
                pairs.setdefault(m.group(1), float(mm.group(1)))
        for m in _RICE_SHORT.finditer(v):
            mm = re.match(r"\s*(?:[=:]\s*)?([+-]?\d+(?:\.\d+)?)", v[m.end():m.end() + 12])
            if mm:
                pairs.setdefault(m.group(1), float(mm.group(1)))
        for m in _PROT_ID.finditer(v):
            mm = re.match(r"\s*(?:[=:]\s*)?([+-]?\d+(?:\.\d+)?)", v[m.end():m.end() + 12])
            if mm:
                pairs.setdefault(m.group(1), float(mm.group(1)))
    return pairs


def contradiction_audit() -> dict:
    """Observational audit over real M evidence ledgers.

    A contradiction is a real E3 measurement of a candidate that the E1 model
    ranked in its top-K, whose measured value is below the median of the measured
    E3 values in the same run. We then check whether a revision record exists and
    whether a revision names the contradicting candidate. We do NOT claim this is
    a controlled injection: the measurements are whatever the agent really
    queried. No measurement is fabricated.
    """
    import statistics

    report = {"kind": "observational_contradiction_audit",
              "note": ("Real E1-vs-E3 contradictions found in existing S1 M runs. "
                       "Not a controlled injection; no measurement is fabricated."),
              "tasks": {}}
    root = ROOT / "results" / "experiments" / "S1"
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        m_dir = task_dir / "M" / "rep0"
        ev_path = m_dir / "evidence.jsonl"
        if not ev_path.exists():
            continue
        e1: dict[str, float] = {}
        e3: dict[str, float] = {}
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            et = r.get("evidence_type")
            pairs = _pairs_from_record(r)
            if et == "E1":
                e1.update(pairs)
            elif et == "E3":
                e3.update(pairs)
        if not e3 or not e1:
            continue
        med = statistics.median(e3.values())
        # top-K of the model's ranking (top quintile of E1 scores, min 5)
        ranked = sorted(e1, key=e1.get, reverse=True)
        k = max(5, len(ranked) // 5)
        topk = set(ranked[:k])
        contradicted = sorted(i for i in topk if i in e3 and e3[i] < med)
        rev_path = m_dir / "revisions.jsonl"
        revisions = 0
        mentions = 0
        if rev_path.exists():
            revs = [json.loads(l) for l in rev_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            revisions = len(revs)
            blob = json.dumps(revs, ensure_ascii=False)
            mentions = sum(1 for i in contradicted if i in blob)
        report["tasks"][task_dir.name] = {
            "run_id": m_dir.name,
            "n_e1_ids": len(e1), "n_e3_measured": len(e3),
            "e3_median": round(med, 4),
            "e1_topk": k,
            "contradicted_top_ids": contradicted[:20],
            "n_contradicted": len(contradicted),
            "revisions_recorded": revisions,
            "contradiction_mentions_in_revisions": mentions,
            "responded": bool(contradicted and (mentions > 0 or revisions > 0)),
        }
    out = ROOT / "results" / "logs" / "scientist_contradiction_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablation", choices=sorted(ABLATIONS), default=None)
    ap.add_argument("--tasks", nargs="+", default=["rice-R2-closed-loop"])
    ap.add_argument("--gen-turns", type=int, default=50)
    ap.add_argument("--gen-budget", type=float, default=4.0)
    ap.add_argument("--contradiction-audit", action="store_true")
    args = ap.parse_args()

    if args.contradiction_audit:
        rep = contradiction_audit()
        for t, r in rep["tasks"].items():
            print(f"[audit] {t}: contradicted={r['n_contradicted']} "
                  f"revisions={r['revisions_recorded']} responded={r['responded']}")
        print(f"wrote results/logs/scientist_contradiction_audit.json")
        return 0

    if not args.ablation:
        ap.error("--ablation or --contradiction-audit is required")
    config.assert_secrets()
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    tasks = [t for t in tasks if t["task_id"] in set(args.tasks)]
    if not tasks:
        print(f"no matching tasks: {args.tasks}")
        return 2
    for task in tasks:
        rec = run_ablation(args.ablation, task, args.gen_turns, args.gen_budget)
        print(f"[S2 {args.ablation}] {rec['task_id']}: gen={rec['generation_status']} "
              f"sisr={rec['sisr']} oracle={rec['oracle_ok']} sev={rec['sev']:.2f} "
              f"rev={rec['revisions']} calls={rec['model_calls']} "
              f"cost=${rec['cost_usd']:.2f} gen_cost=${rec['generation_cost_usd']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
