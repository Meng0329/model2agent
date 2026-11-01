"""Run and score scientist tasks.

The runner only orchestrates real executions and scores them against the hidden
oracle. It never invents a measurement and never edits the agent's answer.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .. import config
from .budget import Budget
from .evidence import EvidenceLedger, RunLedger, new_run_id
from .schemas import EvidenceRecord, RunRecord
from .scorer import ScientificScorer, sev_metrics


def _task_file(task: dict, out: Path) -> Path:
    p = out / "task.json"
    p.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run_scientist_project(project_dir: str | Path, task: dict, run_id: str,
                          out_dir: str | Path, hidden_dir: str | Path,
                          max_turns: int | None = None,
                          max_budget_usd: float | None = None) -> dict:
    """Execute a generated scientist project as an INDEPENDENT subprocess."""
    project_dir = Path(project_dir).resolve()
    out = Path(out_dir).resolve()
    hidden_dir = Path(hidden_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    task_path = _task_file(task, out)
    env = dict(config.agent_env())
    cmd = [sys.executable, str(project_dir / "run_research.py"),
           "--task", str(task_path), "--hidden", str(hidden_dir),
           "--out", str(out), "--run-id", run_id,
           "--max-turns", str(max_turns or config.SCIENTIST_MAX_TURNS),
           "--max-budget-usd", str(max_budget_usd if max_budget_usd is not None
                                   else config.SCIENTIST_MAX_BUDGET_USD)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_dir), env=env,
                          timeout=(config.SCIENTIST_WALL_TIME_S + 300))
    (out / "stderr.log").write_text(proc.stdout + "\n---STDERR---\n" + proc.stderr,
                                    encoding="utf-8")
    return {"returncode": proc.returncode, "latency_s": round(time.perf_counter() - t0, 2),
            "out_dir": str(out)}


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def evaluate_task(task: dict, out_dir: str | Path, hidden_dir: str | Path) -> dict:
    """Independent evaluation against the hidden oracle (evaluator-side only)."""
    out = Path(out_dir)
    hidden_file = Path(hidden_dir) / task["hidden_reference"]
    hidden = json.loads(hidden_file.read_text(encoding="utf-8"))
    final = _load_json(out / "final_selection.json", {}) or {}
    top_ids = final.get("top_ids", []) if isinstance(final, dict) else []
    rule = task.get("input_resources", {}).get("success_rule", {"type": "none"})

    detail: dict[str, Any] = {"rule": rule, "top_ids": top_ids[:20]}
    if rule["type"] == "topk_quartile":
        import numpy as np
        q = float(np.quantile(list(hidden.values()), rule["quartile"]))
        top = top_ids[: rule["k"]]
        hits = sum(1 for i in top if hidden.get(i, float("-inf")) >= q)
        oracle_ok = hits >= rule["min_hits"]
        detail.update({"hits": hits, "k": rule["k"], "min_hits": rule["min_hits"],
                       "threshold": q})
    elif rule["type"] == "rediscovery":
        best = max(hidden, key=hidden.get)
        oracle_ok = bool(top_ids[:1]) and top_ids[0] == best
        detail.update({"best": best, "predicted_best": top_ids[:1]})
    else:
        raise ValueError(f"unknown success rule: {rule['type']}")

    result = _load_json(out / "result.json", {}) or {}
    evidence_rows = []
    ev_path = out / "evidence.jsonl"
    if ev_path.exists():
        evidence_rows = [json.loads(l) for l in ev_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    revisions = 0
    rv_path = out / "revisions.jsonl"
    if rv_path.exists():
        revisions = len([l for l in rv_path.read_text(encoding="utf-8").splitlines() if l.strip()])

    model_calls = int((result.get("budget") or {}).get("model_calls", 0))
    oracle_queries = int((result.get("budget") or {}).get("experiments", 0))
    artifacts = [p.name for p in out.iterdir()] if out.exists() else []
    have_artifacts = all(a in artifacts for a in task.get("expected_artifacts", []))

    evidence = []
    malformed = 0
    for r in evidence_rows:
        try:
            evidence.append(_to_evidence(r))
        except (ValueError, TypeError, KeyError):
            malformed += 1
    sev = sev_metrics(evidence)
    sisr = bool(oracle_ok and model_calls > 0 and evidence_rows and malformed == 0
                and have_artifacts)
    return {
        "oracle_ok": oracle_ok, "sisr_success": sisr, "detail": detail,
        "model_calls": model_calls, "oracle_queries": oracle_queries,
        "evidence_records": len(evidence_rows), "malformed_evidence": malformed,
        "revisions": revisions,
        "artifacts_ok": have_artifacts, "sev": sev,
        "status": result.get("status", "FAILED"),
        "cost_usd": result.get("cost_usd", 0.0),
        "latency_s": result.get("latency_s", 0.0),
        "out_dir": str(out),
    }


def _to_evidence(row: dict) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(row.get("id", "?")), research_question=str(row.get("research_question", "")),
        hypothesis_id=str(row.get("hypothesis_id", "")), experiment_id=str(row.get("experiment_id", "")),
        model=str(row.get("model", "")), input_data=row.get("input_data", {}),
        control_variables=list(row.get("control_variables", [])),
        execution_evidence=str(row.get("execution_evidence", "")),
        observed_result=row.get("observed_result"), evidence_type=row.get("evidence_type", "E1"),
        uncertainty=str(row.get("uncertainty", "")),
        hypothesis_revision=row.get("hypothesis_revision"),
        conclusion=row.get("conclusion"), limitations=list(row.get("limitations", [])),
        timestamp=float(row.get("ts", 0.0)))


def make_run_record(task: dict, method: str, run_id: str, rep: int, evaluation: dict,
                    *, stage: str, agent_generation_status: str,
                    builder_commit: str) -> RunRecord:
    return RunRecord(
        experiment_id=f"{stage}-{task['task_id']}-{method}",
        run_id=run_id, protocol_version="V3.0", stage=stage, method_id=method,
        method_revision="smsc-0.4.0", scientific_domain=task["domain"],
        scientific_model_id=task["scientific_model"], model_revision="pinned",
        scientific_task_id=task["task_id"], task_difficulty=task["capability_level"],
        repetition_id=rep, builder_commit=builder_commit, generated_agent_commit=None,
        sdk_version=_sdk_version(), llm_model_id=config.DEEPSEEK_MODEL,
        prompt_revision="smsc-v1", skill_revision="scientific-v1",
        knowledge_bundle_hash="", dataset_revision="frozen", oracle_revision="v1",
        random_seed=config.RANDOM_SEED,
        resource_budget=task.get("experimental_budget", {}),
        model_call_count=evaluation["model_calls"],
        experiment_count=evaluation["oracle_queries"],
        token_usage=0, cost=float(evaluation.get("cost_usd", 0.0)),
        latency=float(evaluation.get("latency_s", 0.0)),
        agent_generation_status=agent_generation_status,
        scientific_task_success=bool(evaluation.get("sisr_success")),
        hypothesis_validity=None, experiment_validity=evaluation.get("artifacts_ok"),
        evidence_validity=evaluation["sev"]["evidence_validity"],
        adaptation_success=bool(evaluation.get("revisions", 0) > 0),
        final_conclusion_validity=bool(evaluation.get("oracle_ok")),
        failure_category=None if evaluation.get("sisr_success") else "sisr_failed",
        artifact_path=str(evaluation.get("out_dir", "")),
    )


def _sdk_version() -> str:
    try:
        import claude_agent_sdk
        return getattr(claude_agent_sdk, "__version__", "unknown")
    except ImportError:  # pragma: no cover
        return "NOT_INSTALLED"
