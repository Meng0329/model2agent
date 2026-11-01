"""Fair baselines for Model2ScientistBench.

All methods share: the same LLM, the same SDK, the same task, the same resource
budget, the same candidate input, and the same success oracle. Only the method's
structure differs.

  B0  general LLM scientist        — no model tools, no measurement oracle
  B1  LLM + model tools            — run_model + oracle + evidence, no SMSC structure
  B2  direct scientist synthesis   — full workspace + asset, may write its own code/skills
  B3  generic scientist scaffold   — hand-written generic hypothesis/experiment loop
  M   full SMSC                    — generated scientist project (run separately)
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

from .. import config
from .budget import Budget
from .evidence import EvidenceLedger
from ..oracle.historical_oracle import HistoricalOracle
from .sdk_session import build_options, run_session, sdk_version
from .tools import make_scientist_tools


def asset_runner(bundle_dir: str | Path):
    """Load the asset's real infer.py and return a capability runner."""
    bundle_dir = Path(bundle_dir)
    spec = importlib.util.spec_from_file_location(f"m2a_asset_{bundle_dir.name}", bundle_dir / "infer.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    def run(capability: str, args: dict):
        fn = getattr(mod, capability, None)
        if not callable(fn):
            raise AttributeError(f"unknown capability: {capability}")
        return fn(**args)
    return run


def _budget(task: dict) -> Budget:
    b = task.get("experimental_budget", {})
    return Budget(max_tokens=int(b.get("max_tokens", 2_000_000)),
                  max_model_calls=int(b.get("max_model_calls", 64)),
                  max_experiments=int(b.get("oracle_queries", 16)),
                  max_wall_seconds=float(b.get("max_wall_seconds", 1800)),
                  max_usd=float(b.get("max_usd", 2.0)))


def _prompt(task: dict, candidate_file: str, method: str) -> str:
    extra = {
        "B0": ("Work only from the candidate list and your own scientific reasoning. "
               "You have no way to execute the model or measure candidates."),
        "B1": ("Use run_model for real model predictions and query_evidence_oracle for a "
               "budgeted number of real measurements. Record evidence."),
        "B2": ("You have the asset, its documents, and a full workspace. You may write and run "
               "your own analysis code and build whatever research workflow you think is best."),
        "B3": ("Follow a scientific loop: state a falsifiable hypothesis, define an experiment "
               "and its metric, execute with run_model, query real measurements within budget, "
               "record evidence, revise, and conclude."),
    }[method]
    return (f"{task['scientific_question']}\n\nCandidate input file: {candidate_file}\n"
            f"Research budget: {json.dumps(task.get('experimental_budget', {}))}\n"
            f"{extra}\n"
            "Write your final answer to final_selection.json in the working directory as "
            '{"top_ids": [...]}. Do not fabricate measurements; missing values are UNOBSERVABLE.')


def _base_system(method: str, domain: str) -> str:
    return (
        f"You are a {domain} scientist. Ground every claim in real execution. "
        "Model predictions are E1 evidence, never measurements. "
        "Only historical measurements returned by the oracle are E3. "
        "Never invent a value, never simulate a measurement, never use a proxy as if measured. "
        f"Method under evaluation: {method}. The final ranking must be written to "
        "final_selection.json."
    )


async def _run_baseline_async(method: str, task: dict, bundle_dir: Path, out: Path,
                              hidden_dir: Path, run_id: str) -> SessionResult:
    out.mkdir(parents=True, exist_ok=True)
    budget = _budget(task)
    ledger = EvidenceLedger(out / "evidence.jsonl")
    oracle = HistoricalOracle(hidden_dir, measurement_file=task["hidden_reference"],
                              access_log=out / "oracle_access.jsonl", budget=budget,
                              run_id=run_id)
    server = make_scientist_tools(
        spec=task, model_exec=asset_runner(bundle_dir), oracle=oracle, ledger=ledger,
        budget=budget, spec_path=str(out / "plans.jsonl"))
    mcp = {} if method == "B0" else {"m2a_scientist": server}
    options = build_options(
        cwd=out, agents={}, system_prompt=_base_system(method, task["domain"]),
        mcp_servers=mcp,
        max_turns=int((task.get("experimental_budget") or {}).get(
            "max_turns", config.SCIENTIST_MAX_TURNS)),
        max_budget_usd=float((task.get("experimental_budget") or {}).get("max_usd", 2.0)))
    if method == "B0":
        options.tools = ["Read", "Write"]
        options.allowed_tools = ["Read", "Write"]
    res = await run_session(
        _prompt(task, task["input_resources"]["candidate_file"], method), options)
    (out / "result.json").write_text(json.dumps({
        "run_id": run_id, "status": "OBSERVED" if not res.is_error else "FAILED",
        "text": res.text, "cost_usd": res.cost_usd, "num_turns": res.num_turns,
        "session_id": res.session_id, "latency_s": round(res.latency_ms / 1000, 2),
        "budget": budget.as_dict(), "sdk_version": sdk_version(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "trajectory.jsonl").write_text(
        "\n".join(json.dumps({"name": t.name, "status": t.status, "is_error": t.is_error})
                  for t in res.tool_events), encoding="utf-8")
    return res


def run_baseline(method: str, task: dict, bundle_dir: str | Path, out_dir: str | Path,
                 hidden_dir: str | Path, run_id: str) -> dict:
    if method == "M":
        raise ValueError("M is a generated project: use runner.run_scientist_project")
    t0 = time.perf_counter()
    res = asyncio.run(_run_baseline_async(method, task, Path(bundle_dir), Path(out_dir),
                                          Path(hidden_dir), run_id))
    return {"returncode": 0 if not res.is_error else 1,
            "latency_s": round(time.perf_counter() - t0, 2), "out_dir": str(out_dir)}
