"""Aggregate scientist run records into per-method/per-domain metrics.

Reads the append-only raw records; never fabricates a number. Reports SISR,
oracle success, SEV, cost, latency, and paired M-vs-baseline differences with
honest (small-n) caveats.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "results" / "logs" / "scientist_runs.jsonl"
CSV = ROOT / "results" / "csv" / "scientist_summary.csv"
JSON_OUT = ROOT / "results" / "logs" / "scientist_analysis.json"


def _rate(xs: list[bool]) -> float:
    return sum(1 for x in xs if x) / len(xs) if xs else 0.0


def main() -> None:
    if not LOG.exists():
        print("no runs yet: ", LOG)
        return
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Harness defects (output path / budget cap) are real runs but not evidence
    # about the method; keep them out of method comparisons.
    rows = [r for r in rows if not str(r.get("failure_category") or "").startswith("harness_")]

    # per (task, method)
    by_key = {}
    for r in rows:
        k = (r["scientific_task_id"], r["method_id"])
        by_key.setdefault(k, []).append(r)

    table = []
    for (task, method), rs in sorted(by_key.items()):
        sisr = _rate([bool(r["scientific_task_success"]) for r in rs])
        oracle = _rate([bool(r["final_conclusion_validity"]) for r in rs])
        sev = statistics.mean([float(r["evidence_validity"] or 0.0) for r in rs])
        table.append({
            "task_id": task, "method": method, "n": len(rs),
            "sisr_rate": round(sisr, 3), "oracle_ok_rate": round(oracle, 3),
            "mean_sev": round(sev, 3), "mean_cost_usd": round(
                statistics.mean([float(r["cost"] or 0.0) for r in rs]), 4),
            "mean_latency_s": round(statistics.mean([float(r["latency"] or 0.0) for r in rs]), 1),
            "mean_model_calls": round(statistics.mean([int(r["model_call_count"] or 0) for r in rs]), 1),
        })

    # per-method across tasks + per-domain macro-avg
    by_method = {}
    for r in rows:
        by_method.setdefault(r["method_id"], []).append(r)
    methods = {}
    for m, rs in by_method.items():
        methods[m] = {"n": len(rs), "sisr_rate": round(_rate([bool(r["scientific_task_success"]) for r in rs]), 3),
                      "oracle_ok_rate": round(_rate([bool(r["final_conclusion_validity"]) for r in rs]), 3),
                      "mean_sev": round(statistics.mean([float(r["evidence_validity"] or 0.0) for r in rs]), 3),
                      "mean_cost_usd": round(statistics.mean([float(r["cost"] or 0.0) for r in rs]), 4)}

    # domain macro-avg of SISR PER METHOD (each domain weighted equally)
    method_dom = {}
    for r in rows:
        method_dom.setdefault(r["method_id"], {}).setdefault(r["scientific_domain"], []).append(r)
    by_method_domain = {
        m: {d: {"n": len(rs),
                "sisr_rate": round(_rate([bool(x["scientific_task_success"]) for x in rs]), 3)}
            for d, rs in doms.items()}
        for m, doms in method_dom.items()
    }
    domain_macro_by_method = {
        m: round(statistics.mean([v["sisr_rate"] for v in d.values()]), 3)
        for m, d in by_method_domain.items()
    }
    # pooled (all methods) kept only for transparency, NOT the headline number
    dom = {}
    for r in rows:
        dom.setdefault(r["scientific_domain"], []).append(r)
    domains_pooled = {d: {"n": len(rs), "sisr_rate": round(_rate([bool(r["scientific_task_success"]) for r in rs]), 3)}
                      for d, rs in dom.items()}

    # paired M vs each baseline, per task (only tasks with both)
    paired = {}
    tasks = sorted({r["scientific_task_id"] for r in rows})
    for t in tasks:
        mrows = by_key.get((t, "M"), [])
        for b in ("B0", "B1", "B2", "B3"):
            brows = by_key.get((t, b), [])
            if not mrows or not brows:
                continue
            paired[f"{t}:{b}"] = {
                "m_sisr": round(_rate([bool(r["scientific_task_success"]) for r in mrows]), 3),
                f"{b}_sisr": round(_rate([bool(r["scientific_task_success"]) for r in brows]), 3),
                "delta": round(_rate([bool(r["scientific_task_success"]) for r in mrows])
                               - _rate([bool(r["scientific_task_success"]) for r in brows]), 3),
                "n_m": len(mrows), "n_b": len(brows)}

    out = {"n_runs": len(rows), "table": table, "by_method": methods,
           "by_domain_pooled": domains_pooled,
           "by_method_domain": by_method_domain,
           "domain_macro_sisr_by_method": domain_macro_by_method,
           "paired": paired,
           "note": "n_models=2; n_reps=1; small-n descriptive only, no cross-domain significance claim"}
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["task_id,method,n,sisr_rate,oracle_ok_rate,mean_sev,mean_cost_usd,mean_latency_s"]
    for row in table:
        lines.append(",".join(str(row[k]) for k in
                              ("task_id", "method", "n", "sisr_rate", "oracle_ok_rate",
                               "mean_sev", "mean_cost_usd", "mean_latency_s")))
    CSV.parent.mkdir(parents=True, exist_ok=True)
    CSV.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"n_runs": len(rows), "by_method": methods,
                      "by_method_domain": by_method_domain,
                      "domain_macro_sisr_by_method": domain_macro_by_method,
                      "paired": paired}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
