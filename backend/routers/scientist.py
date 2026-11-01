"""Read-only scientist-benchmark API (S1 dashboard).

Serves the frozen Model2ScientistBench and the append-only run ledger so the
frontend can show real, honest results. No writes here — results are produced
by scripts/run_scientist_pilot.py and scored by the evaluator.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config

router = APIRouter(prefix="/api/scientist", tags=["scientist"])

TASKS = config.SCIENTIST_TASKS_PATH
LOG = config.SCIENTIST_RUN_LOG
EXPERIMENTS = config.ROOT / "results" / "experiments"

METHODS = ["B0", "B1", "B2", "B3", "M"]
_SAFE = ("harness_output_path_bug", "harness_budget_cap")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_lines(path: Path, limit: int = 200):
    if not path.exists():
        return []
    rows = []
    for l in path.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        try:
            rows.append(json.loads(l))
        except json.JSONDecodeError:
            continue
        if len(rows) >= limit:
            break
    return rows


def _summarize(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {"n": 0, "sisr_rate": None, "oracle_ok_rate": None, "mean_sev": None,
                "mean_cost_usd": None, "mean_latency_s": None, "status": "NOT_TESTED"}
    def rate(k):
        return round(sum(1 for r in records if r.get(k)) / n, 3)
    def mean(k):
        return round(sum(float(r.get(k) or 0) for r in records) / n, 3)
    any_ok = any(r.get("scientific_task_success") for r in records)
    return {
        "n": n,
        "sisr_rate": rate("scientific_task_success"),
        "oracle_ok_rate": rate("final_conclusion_validity"),
        "mean_sev": mean("evidence_validity"),
        "mean_cost_usd": mean("cost"),
        "mean_latency_s": mean("latency"),
        "status": "OBSERVED" if any_ok else "FAILED",
    }


def _public_task(t: dict) -> dict:
    # hidden_reference points into the 0700 oracle store; expose only that it exists.
    return {
        "task_id": t["task_id"], "domain": t["domain"],
        "scientific_model": t["scientific_model"], "split": t.get("split"),
        "capability_level": t.get("capability_level"),
        "scientific_question": t.get("scientific_question"),
        "success_rule": t.get("input_resources", {}).get("success_rule"),
        "budget": t.get("experimental_budget", {}),
        "has_hidden_oracle": bool(t.get("hidden_reference")),
        "expected_artifacts": t.get("expected_artifacts", []),
    }


@router.get("/benchmark")
def benchmark():
    tasks = _load(TASKS, {}).get("tasks", [])
    records = _load_lines(LOG, limit=4000)
    # separate harness-defect runs; they are preserved but not method evidence
    normal = [r for r in records if not str(r.get("failure_category") or "").startswith("harness_")]
    harness = [r for r in records if str(r.get("failure_category") or "").startswith("harness_")]

    cells = {}
    for r in normal:
        key = (r["scientific_task_id"], r["method_id"])
        cells.setdefault(key, []).append(r)

    by_method = {}
    for m in METHODS:
        mr = [r for r in normal if r["method_id"] == m]
        by_method[m] = _summarize(mr)

    task_cells = {}
    for t in tasks:
        tid = t["task_id"]
        for m in METHODS:
            rs = cells.get((tid, m), [])
            task_cells.setdefault(tid, {})[m] = (
                _summarize(rs) if rs else {"n": 0, "status": "NOT_TESTED"})

    return {
        "tasks": [_public_task(t) for t in tasks],
        "by_method": by_method,
        "cells": task_cells,
        "n_runs": len(normal),
        "n_harness_runs": len(harness),
    }


@router.get("/runs")
def runs():
    records = _load_lines(LOG, limit=4000)
    out = []
    for r in records:
        out.append({
            "run_id": r.get("run_id"), "stage": r.get("stage"),
            "method_id": r.get("method_id"), "scientific_task_id": r.get("scientific_task_id"),
            "scientific_domain": r.get("scientific_domain"),
            "scientific_task_success": bool(r.get("scientific_task_success")),
            "final_conclusion_validity": bool(r.get("final_conclusion_validity")),
            "evidence_validity": r.get("evidence_validity"),
            "model_call_count": r.get("model_call_count"),
            "experiment_count": r.get("experiment_count"),
            "adaptation_success": bool(r.get("adaptation_success")),
            "cost": r.get("cost"), "latency": r.get("latency"),
            "failure_category": r.get("failure_category"),
            "notes": r.get("notes"),
            "artifact_path": r.get("artifact_path"),
        })
    return {"runs": out}


@router.get("/runs/{run_id}")
def run_detail(run_id: str):
    records = _load_lines(LOG, limit=4000)
    rec = next((r for r in records if r.get("run_id") == run_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail=f"no such run: {run_id}")

    base = Path(rec.get("artifact_path") or "")
    # guard: only expose artifacts under results/experiments
    try:
        base = base.resolve()
    except Exception:
        base = base.absolute()
    if not str(base).startswith(str(EXPERIMENTS.resolve())):
        base = None

    detail = {
        "run": {k: rec.get(k) for k in (
            "run_id", "stage", "method_id", "method_revision", "scientific_task_id",
            "scientific_domain", "scientific_model_id", "task_difficulty", "repetition_id",
            "builder_commit", "sdk_version", "llm_model_id", "resource_budget",
            "model_call_count", "experiment_count", "cost", "latency",
            "scientific_task_success", "final_conclusion_validity", "evidence_validity",
            "agent_generation_status",
            "adaptation_success", "failure_category", "notes", "artifact_path")},
        "result": None, "conclusions": [], "evidence": [], "final_selection": None,
        "revisions": [], "oracle_queries": None, "harness_artifact_note": "",
    }
    if base and base.exists():
        detail["result"] = _load(base / "result.json", None)
        detail["conclusions"] = _load_lines(base / "conclusions.jsonl")
        detail["evidence"] = _load_lines(base / "evidence.jsonl")
        detail["final_selection"] = _load(base / "final_selection.json", None)
        detail["revisions"] = _load_lines(base / "revisions.jsonl")
        oa = _load_lines(base / "oracle_access.jsonl", limit=4096)
        detail["oracle_queries"] = len(oa)
        if rec.get("failure_category") in _SAFE:
            detail["harness_artifact_note"] = (
                "this run was affected by a fixed harness defect and is excluded from "
                "method comparisons (see docs/scientist_protocol.md).")
    return detail
