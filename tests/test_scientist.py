"""S0 gate tests for the Model-to-Scientist research layer.

These tests enforce: typed schemas, grounded introspection, strict oracles,
budget enforcement, hidden-store isolation, and 'no silent fallback' behaviour.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from model2agent.scientist.schemas import (
    EvidenceRecord, Hypothesis, ResearchCapabilityEdge, ResearchCapabilityGraph,
    ResearchCapabilityNode, ScientificAffordance, TaskSpec,
)
from model2agent.scientist.budget import Budget, BudgetExceeded
from model2agent.scientist.scorer import ScientificScorer, sev_metrics
from model2agent.scientist.model_introspection import inspect_model
from model2agent.oracle.execution_oracle import ExecutionOracle, compare_values
from model2agent.oracle.historical_oracle import HistoricalOracle, UNOBSERVABLE

ROOT = Path(__file__).resolve().parents[1]


def _task(**kw):
    base = dict(
        task_id="t1", domain="protein", scientific_model="esm2",
        scientific_question="q", input_resources={}, allowed_knowledge=[],
        available_tools=["run_model"], experimental_budget={"oracle": 8},
        permitted_actions=["run_model"], hidden_reference="t1.json",
        execution_oracle="reference_exec", evidence_oracle="historical",
        success_criteria=["nonzero model call"], scientific_constraints=[],
        expected_artifacts=[], failure_conditions=[],
    )
    base.update(kw)
    return TaskSpec(**base)


def test_task_spec_requires_criteria_and_rejects_unknown_oracle():
    with pytest.raises(ValueError, match="success criteria"):
        _task(success_criteria=[])
    with pytest.raises(ValueError, match="unknown execution oracle"):
        _task(execution_oracle="magic")


def test_hypothesis_must_be_falsifiable():
    with pytest.raises(ValueError, match="falsifiable"):
        Hypothesis(id="h1", question="q", statement="s", testable=True,
                   falsifier="", predicted_observation="x")


def test_affordance_verified_requires_evidence():
    with pytest.raises(ValueError, match="verification_evidence"):
        ScientificAffordance(id="a1", model="m", scientific_task="score",
                             input_spec={}, output_spec={}, preconditions=[],
                             tool="infer.score", scientific_constraints=[],
                             evidence_source="card", uncertainty="low",
                             verified=True)


def test_capability_graph_rejects_dangling_edge():
    n = [ResearchCapabilityNode(id="a", kind="model_tool", description="d", io={})]
    with pytest.raises(ValueError, match="unknown node"):
        ResearchCapabilityGraph(slug="s", nodes=n,
                                edges=[ResearchCapabilityEdge(src="a", dst="b")],
                                roots=["a"])


def test_evidence_rejects_E3_without_trace():
    with pytest.raises(ValueError, match="traceable"):
        EvidenceRecord(id="e", research_question="q", hypothesis_id="h",
                       experiment_id="x", model="m", input_data={},
                       control_variables=[], execution_evidence="",
                       observed_result=1, evidence_type="E3", uncertainty="u",
                       hypothesis_revision=None, conclusion=None, limitations=[],
                       timestamp=0.0)


def test_compare_values_is_strict():
    assert compare_values({"a": 1.0}, {"a": 1.0000001}, 1e-3, 1e-6)
    assert not compare_values({"a": 1.0}, {"a": 1.1}, 1e-3, 1e-6)
    assert not compare_values({"a": 1.0}, {"b": 1.0}, 1e-3, 1e-6)


def test_execution_oracle_rejects_none_and_matches_real_model():
    cnn = ROOT / "model_assets" / "cnn_digits"
    if not cnn.exists():
        pytest.skip("cnn_digits asset not present")
    ex = json.loads((cnn / "examples.json").read_text())["predict"][0]["args"]
    oracle = ExecutionOracle(cnn)
    ref = oracle.reference("predict", ex)
    ok, _ = oracle.compare("predict", ex, ref)
    assert ok
    ok_none, detail = oracle.compare("predict", ex, None)
    assert not ok_none and "None" in detail["reason"]
    ok_bad, _ = oracle.compare("predict", ex, "definitely-wrong")
    assert not ok_bad


def test_introspection_is_grounded():
    cnn = ROOT / "model_assets" / "cnn_digits"
    if not cnn.exists():
        pytest.skip("cnn_digits asset not present")
    facts = inspect_model(cnn)
    assert facts.import_error is None
    assert "predict" in facts.real_callables()
    assert facts.weights_sha256
    assert any(e.capability == "predict" and e.ok for e in facts.executed_examples)


def _hidden(tmp_path: Path, payload: dict) -> Path:
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    os.chmod(hidden, stat.S_IRWXU)  # 0700
    (hidden / "task.json").write_text(json.dumps(payload))
    return hidden


def test_historical_oracle_budget_and_unobservable(tmp_path):
    hidden = _hidden(tmp_path, {"c1": 0.9})
    budget = Budget(max_tokens=10**9, max_model_calls=10**9, max_experiments=2,
                    max_wall_seconds=10**9, max_usd=10**9)
    oracle = HistoricalOracle(hidden, measurement_file="task.json",
                              access_log=tmp_path / "access.jsonl",
                              budget=budget, run_id="r1")
    val, source = oracle.measure("c1")
    assert val == 0.9 and source == "E3"
    assert oracle.measure("c_missing")[0] == UNOBSERVABLE
    with pytest.raises(BudgetExceeded):
        oracle.measure("c1")  # third query exceeds max_experiments=2
    log = [json.loads(l) for l in (tmp_path / "access.jsonl").read_text().splitlines()]
    assert len(log) == 2 and log[0]["run_id"] == "r1"


def test_historical_oracle_rejects_path_traversal(tmp_path):
    hidden = _hidden(tmp_path, {})
    budget = Budget(max_tokens=10**9, max_model_calls=10**9, max_experiments=99,
                    max_wall_seconds=10**9, max_usd=10**9)
    oracle = HistoricalOracle(hidden, measurement_file="task.json",
                              access_log=tmp_path / "a.jsonl", budget=budget, run_id="r")
    with pytest.raises(ValueError, match="invalid oracle key"):
        oracle._load("../secret.json")


def test_historical_oracle_requires_0700(tmp_path):
    hidden = tmp_path / "loose"
    hidden.mkdir()
    os.chmod(hidden, 0o755)
    budget = Budget(max_tokens=1, max_model_calls=1, max_experiments=1,
                    max_wall_seconds=1, max_usd=1)
    with pytest.raises(PermissionError, match="0700"):
        HistoricalOracle(hidden, measurement_file="x.json",
                         access_log=tmp_path / "a.jsonl", budget=budget, run_id="r")


def test_scorer_fails_run_without_model_calls():
    spec = _task()
    verdict = ScientificScorer(spec).score("r1", model_call_count=0, evidence=[], artifacts=[])
    assert not verdict.sisr_success
    assert verdict.failure_category == "real_model_execution"


def test_sev_reports_unsupported_rate():
    rec = EvidenceRecord(
        id="e1", research_question="q", hypothesis_id="h1", experiment_id="x1",
        model="m", input_data={}, control_variables=[], execution_evidence="trace.json",
        observed_result=1, evidence_type="E1", uncertainty="model-only",
        hypothesis_revision=None, conclusion="c", limitations=[], timestamp=1.0)
    metrics = sev_metrics([rec])
    assert metrics["evidence_validity"] == 1.0
    assert metrics["unsupported_claim_rate"] == 0.0
