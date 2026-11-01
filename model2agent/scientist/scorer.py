"""Deterministic scoring of scientist runs (SISR / SEV).

All checks are mechanical and pre-registered; nothing is judged by prose quality.
A run that produced no real model call is FAILED by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import EvidenceRecord, TaskSpec


@dataclass
class RunVerdict:
    run_id: str
    task_id: str
    sisr_success: bool
    sisr_checks: dict[str, bool] = field(default_factory=dict)
    model_call_count: int = 0
    evidence_records: int = 0
    supported_conclusions: int = 0
    total_conclusions: int = 0
    failure_category: str | None = None


class ScientificScorer:
    """Scores a single run against its frozen TaskSpec."""

    def __init__(self, spec: TaskSpec):
        self.spec = spec

    def score(self, run_id: str, *, model_call_count: int,
              evidence: list[EvidenceRecord], artifacts: list[str]) -> RunVerdict:
        checks: dict[str, bool] = {}
        # 1. real model execution happened
        checks["real_model_execution"] = model_call_count > 0
        # 2. at least one evidence record exists
        checks["evidence_recorded"] = len(evidence) > 0
        # 3. at least one conclusion is evidence-supported
        concluded = [e for e in evidence if e.conclusion]
        supported = [e for e in concluded if e.execution_evidence and e.evidence_type in ("E1", "E2", "E3", "E4")]
        checks["conclusion_supported"] = bool(supported)
        # 4. required artifacts produced
        have = set(artifacts)
        checks["artifacts"] = all(a in have for a in self.spec.expected_artifacts) if self.spec.expected_artifacts else True
        # 5. explicit success criteria (e.g. oracle agreement threshold) — checked by caller via oracle
        success = all(checks.values())
        failure = None if success else next((k for k, v in checks.items() if not v), None)
        return RunVerdict(
            run_id=run_id, task_id=self.spec.task_id, sisr_success=success,
            sisr_checks=checks, model_call_count=model_call_count,
            evidence_records=len(evidence),
            supported_conclusions=len(supported), total_conclusions=len(concluded),
            failure_category=failure,
        )


def sev_metrics(evidence: list[EvidenceRecord]) -> dict[str, float]:
    """Scientific Evidence Validity: supported share + unsupported claim rate."""
    concluded = [e for e in evidence if e.conclusion]
    supported = [e for e in concluded if e.execution_evidence and e.evidence_type in ("E1", "E2", "E3", "E4")]
    total = len(concluded)
    return {
        "evidence_validity": (len(supported) / total) if total else 0.0,
        "unsupported_claim_rate": (1.0 - len(supported) / total) if total else 0.0,
        "n_conclusions": total,
        "n_supported": len(supported),
    }


def sev_from_conclusions(conclusions: list[dict], evidence: list[EvidenceRecord]) -> dict[str, float]:
    """SEV over the agent's conclusion channel.

    A conclusion counts as supported only when every cited evidence id exists in
    the ledger AND every declared evidence type matches the ledger record's own
    type. A conclusion with an unresolvable citation is unsupported, not ignored.
    """
    by_id = {e.id: e for e in evidence}
    total = 0
    supported = 0
    for c in conclusions:
        if not isinstance(c, dict):
            continue
        total += 1
        ids = c.get("supporting_evidence") or c.get("supporting_records") or []
        types = c.get("evidence_types") or []
        statement = c.get("statement") or c.get("claim")
        if not ids or not statement:
            continue
        cited = [by_id.get(str(i)) for i in ids]
        if any(r is None for r in cited):
            continue
        if types and not set(map(str, types)).issubset({r.evidence_type for r in cited if r}):
            continue
        supported += 1
    return {
        "evidence_validity": (supported / total) if total else 0.0,
        "unsupported_claim_rate": (1.0 - supported / total) if total else 0.0,
        "n_conclusions": total,
        "n_supported": supported,
    }
