"""Benchmark runner — executes methods B0 (raw assets), B2 (direct synthesis),
and M (full Model2Agent) on frozen tasks, 5 reps each. Ground truth is always the
original model's reference execution. Raw per-rep records -> JSONL for statistics.
"""
from __future__ import annotations
import json, time, importlib.util
from pathlib import Path

from .. import config
from ..agci.asset_scanner import scan_bundle
from ..verification.reference_exec import compare, run_reference
from ..baselines import b0_run, b2_run
from ..orchestrator import run_method_m
from ..llm import LLMClient, scrub
from ..config import LLM_USD_PER_M_INPUT, LLM_USD_PER_M_OUTPUT


def _load_agent_module(slug):
    p = config.GENERATED_AGENTS_DIR / slug / "agent.py"
    spec = importlib.util.spec_from_file_location(f"m2a_agent_{slug}", p)
    mod = importlib.util.module_from_spec(spec); sys_register(mod, spec)
    spec.loader.exec_module(mod)
    return mod


def sys_register(mod, spec):
    import sys
    sys.modules[spec.name] = mod


def _nl(task):
    """nl_prompt from either a frozen-task dict or a Task object."""
    return task["nl_prompt"] if isinstance(task, dict) else task.nl_prompt


def _exec_m(agent_mod, task):
    r = agent_mod.query(_nl(task))
    got = r.get("result") if r.get("ok") else None
    return {"ok": bool(r.get("ok")), "got": got, "tokens": r.get("tokens", 0),
            "latency_ms": r.get("latency_ms", 0.0), "error": r.get("error")}


def _exec_llm_method(method, llm, desc, task):
    if method == "B0":
        r = b0_run(llm, desc.bundle_dir, desc.card_text, desc.functions, task, _nl(task))
    elif method == "B1":
        from ..baselines.b1_generic_wrapper import run_task as b1_run
        r = b1_run(llm, desc.bundle_dir, desc.card_text, desc.functions, task, _nl(task))
    else:
        r = b2_run(llm, desc.bundle_dir, desc.card_text, desc.functions, task, _nl(task))
    got = r.get("got")
    return {"ok": got is not None and "error" not in r, "got": got, "detail": r}


def _m_cost(tokens):
    return tokens / 1_000_000 * ((LLM_USD_PER_M_INPUT + LLM_USD_PER_M_OUTPUT) / 2)


def run_benchmark(slugs, methods=("B0", "B2", "M"), reps=5, tasks_path=None, log_path=None):
    log_path = Path(log_path) if log_path else config.LOGS_DIR / "pilot_runs.jsonl"
    tasks_path = Path(tasks_path) if tasks_path else config.ROOT / "results" / "frozen" / "tasks.json"
    db = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks_by_slug = {}
    for t in db["tasks"]:
        tasks_by_slug.setdefault(t["slug"], []).append(t)
    cap_examples = db.get("capability_examples", {})

    llm = {m: LLMClient(m) for m in methods if m != "M"}
    summary = {m: {"agentified": 0, "task_correct": 0, "task_total": 0, "cap_ok": 0, "cap_total": 0,
                   "cost_usd": 0.0, "latency_ms": 0.0} for m in methods}

    for slug in slugs:
        bdir = config.MODEL_ASSETS_DIR / slug
        desc = scan_bundle(bdir)

        # --- M agentification (full pipeline, once) ---
        m_res = run_method_m(bdir, llm=llm.setdefault("M", LLMClient("M")), verify=True, repair=True)
        summary["M"]["agentified"] += int(bool(m_res.get("success")))
        _log(log_path, {"record_type": "agentification", "method": "M", "slug": slug,
                        "success": bool(m_res.get("success")),
                        "cap_verification_rate": m_res.get("capability_verification_rate"),
                        "cap_verification_rate_all": m_res.get("capability_verification_rate_all"),
                        "steps": scrub_json(m_res.get("steps", {}))})

        agent_mod = None
        if m_res.get("success") or (config.GENERATED_AGENTS_DIR / slug / "agent.py").exists():
            try:
                agent_mod = _load_agent_module(slug)
            except Exception as e:
                _log(log_path, {"record_type": "agent_load_error", "method": "M", "slug": slug,
                                "error": scrub(f"{type(e).__name__}: {e}")})

        # --- capability verification (all methods, one example per capability) ---
        for cap, cex in cap_examples.get(slug, {}).items():
            if "error" in cex:
                continue
            for method in methods:
                ok, got, cost, lat = _exec_capability(method, llm, desc, agent_mod, cap, cex)
                summary[method]["cost_usd"] += cost
                summary[method]["latency_ms"] += lat
                summary[method]["cap_total"] += 1
                summary[method]["cap_ok"] += int(ok)
                _log(log_path, {"record_type": "capability_verify", "method": method, "slug": slug,
                                "capability": cap, "reference": str(cex["reference_output"])[:200],
                                "got": str(got)[:200], "ok": ok, "correct": ok,
                                "llm_cost_usd": cost, "latency_ms": lat})

        # --- task runs (reps) ---
        for task in tasks_by_slug.get(slug, []):
            gt = task["reference_output"]
            for method in methods:
                for rep in range(reps):
                    cost = lat = 0.0; ok = False; got = None
                    try:
                        if method == "M":
                            if agent_mod is None:
                                r = {"ok": False, "error": "no_agent"}
                            else:
                                r = _exec_m(agent_mod, task)
                            cost = _m_cost(r.get("tokens", 0)); lat = r.get("latency_ms", 0.0)
                        else:
                            t0 = time.perf_counter()
                            before = llm[method].total_cost()
                            r = _exec_llm_method(method, llm[method], desc, task)
                            lat = (time.perf_counter() - t0) * 1000
                            cost = llm[method].total_cost() - before
                        got = r.get("got")
                        ok = bool(r.get("ok")) and _compare(task["capability"], gt, got)
                    except Exception as e:
                        r = {"error": scrub(f"{type(e).__name__}: {e}")}
                    summary[method]["task_total"] += 1
                    summary[method]["task_correct"] += int(ok)
                    summary[method]["cost_usd"] += cost
                    summary[method]["latency_ms"] += lat
                    _log(log_path, {"record_type": "task_run", "method": method, "slug": slug,
                                    "task_id": task["task_id"], "split": task["split"], "rep": rep,
                                    "capability": task["capability"], "reference_output": str(gt)[:200],
                                    "got": str(got)[:200], "ok": bool(r.get("ok", False)), "correct": ok,
                                    "error": scrub(str(r.get("error") or (r.get("detail") or {}).get("stderr") or (r.get("detail") or {}).get("error") or ""))[:300],
                                    "llm_cost_usd": cost, "latency_ms": lat})
    return summary


def _exec_capability(method, llm, desc, agent_mod, cap, cex):
    from .tasks import Task
    t = Task(task_id=f"cap-{cap}", slug=desc.slug, split="capability", capability=cap,
             args=cex["args"], reference_output=cex["reference_output"], check="exact",
             nl_prompt=cex["nl_prompt"])
    cost = lat = 0.0
    try:
        if method == "M":
            if agent_mod is None:
                return False, None, 0.0, 0.0
            r = _exec_m(agent_mod, t); cost = _m_cost(r.get("tokens", 0)); lat = r.get("latency_ms", 0.0)
            got = r.get("got")
        else:
            t0 = time.perf_counter(); before = llm[method].total_cost()
            r = _exec_llm_method(method, llm[method], desc, t)
            lat = (time.perf_counter() - t0) * 1000; cost = llm[method].total_cost() - before
            got = r.get("got")
        ok = bool(r.get("ok")) and _compare(cap, cex["reference_output"], got)
        return ok, got, cost, lat
    except Exception as e:
        return False, None, 0.0, 0.0


def _compare(cap, ref, got):
    try:
        return compare(cap, ref, got)
    except Exception:
        return False


def _log(path, obj):
    obj = dict(obj); obj.setdefault("ts", time.time())
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def scrub_json(obj):
    return json.loads(scrub(json.dumps(obj, ensure_ascii=False, default=str)))
