"""Deterministic tests for the scientist runner scoring and benchmark integrity."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from model2agent.scientist.runner import evaluate_task, _to_evidence
from model2agent.scientist.scorer import sev_metrics

ROOT = Path(__file__).resolve().parents[1]


def _hidden(tmp_path: Path, payload: dict) -> Path:
    h = tmp_path / "hidden"
    h.mkdir()
    os.chmod(h, stat.S_IRWXU)
    (h / "o.json").write_text(json.dumps(payload), encoding="utf-8")
    return h


def _task(task_id, rule) -> dict:
    return {"task_id": task_id, "domain": "x", "scientific_model": "m",
            "scientific_question": "q", "input_resources": {"success_rule": rule},
            "allowed_knowledge": [], "available_tools": [], "experimental_budget": {},
            "permitted_actions": [], "hidden_reference": "o.json",
            "execution_oracle": "reference_exec", "evidence_oracle": "historical",
            "success_criteria": ["c"], "scientific_constraints": [],
            "expected_artifacts": ["evidence.jsonl", "conclusions.jsonl", "final_selection.json"],
            "failure_conditions": []}


def _write_run(out: Path, top_ids, model_calls=5, evidence=None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "final_selection.json").write_text(json.dumps({"top_ids": top_ids}), encoding="utf-8")
    (out / "result.json").write_text(json.dumps({
        "status": "OBSERVED", "cost_usd": 0.1, "latency_s": 5.0,
        "budget": {"model_calls": model_calls, "experiments": 4}}), encoding="utf-8")
    (out / "conclusions.jsonl").write_text("x\n", encoding="utf-8")
    ev = evidence or [{"research_question": "q", "hypothesis_id": "h", "experiment_id": "e",
                       "model": "m", "input_data": {}, "control_variables": [],
                       "execution_evidence": "trace", "observed_result": 1,
                       "evidence_type": "E1", "uncertainty": "u", "conclusion": "c",
                       "limitations": [], "ts": 1.0}]
    (out / "evidence.jsonl").write_text(
        "\n".join(json.dumps(r) for r in ev), encoding="utf-8")


def test_topk_quartile_success(tmp_path):
    hidden = _hidden(tmp_path, {f"c{i}": float(i) for i in range(20)})
    rule = {"type": "topk_quartile", "k": 4, "min_hits": 3, "quartile": 0.75}
    out = tmp_path / "out"
    _write_run(out, ["c19", "c18", "c17", "c16"])
    ev = evaluate_task(_task("t", rule), out, hidden)
    assert ev["oracle_ok"] and ev["sisr_success"] and ev["detail"]["hits"] == 4


def test_topk_quartile_failure_no_model_calls(tmp_path):
    hidden = _hidden(tmp_path, {f"c{i}": float(i) for i in range(20)})
    rule = {"type": "topk_quartile", "k": 4, "min_hits": 3, "quartile": 0.75}
    out = tmp_path / "out"
    _write_run(out, ["c19", "c18", "c17", "c16"], model_calls=0)
    ev = evaluate_task(_task("t", rule), out, hidden)
    assert ev["oracle_ok"] and not ev["sisr_success"]   # success impossible without real model calls


def test_rediscovery(tmp_path):
    hidden = _hidden(tmp_path, {"a": 1.0, "b": 9.0, "c": 5.0})
    rule = {"type": "rediscovery", "k": 1}
    out = tmp_path / "out"
    _write_run(out, ["b"])
    ev = evaluate_task(_task("t", rule), out, hidden)
    assert ev["oracle_ok"] and ev["sisr_success"]
    _write_run(out, ["c"])
    ev = evaluate_task(_task("t", rule), out, hidden)
    assert not ev["oracle_ok"]


def test_missing_final_selection(tmp_path):
    hidden = _hidden(tmp_path, {"a": 1.0, "b": 9.0})
    rule = {"type": "rediscovery", "k": 1}
    out = tmp_path / "out"
    out.mkdir(parents=True)
    (out / "result.json").write_text(json.dumps({"status": "OBSERVED", "cost_usd": 0.1,
        "latency_s": 5.0, "budget": {"model_calls": 3, "experiments": 1}}), encoding="utf-8")
    (out / "evidence.jsonl").write_text("{}", encoding="utf-8")
    (out / "conclusions.jsonl").write_text("x\n", encoding="utf-8")
    ev = evaluate_task(_task("t", rule), out, hidden)
    assert not ev["artifacts_ok"] and not ev["sisr_success"]


def test_frozen_tasks_have_unique_ids_and_no_leakage():
    f = ROOT / "results" / "frozen" / "scientist_tasks.json"
    if not f.exists():
        pytest.skip("frozen tasks not built yet")
    data = json.loads(f.read_text(encoding="utf-8"))
    tasks = data["tasks"]
    ids = [t["task_id"] for t in tasks]
    assert len(ids) == len(set(ids))
    for t in tasks:
        assert "final_selection.json" in t["expected_artifacts"]
        assert t["input_resources"]["success_rule"]["type"] in ("topk_quartile", "rediscovery")
    # the candidate input files must not carry any measured value
    inputs = ROOT / "m2a_data" / "research" / "inputs"
    for p in inputs.glob("*.json"):
        blob = p.read_text(encoding="utf-8")
        assert "DMS_score" not in blob and "GRWT100" not in p.name  # names ok, columns not
