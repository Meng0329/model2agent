"""Immutable run records + the Scientific Evidence Ledger.

Raw records are append-only. A summary may be recomputed, but the raw JSONL is
never rewritten and every reported number must trace back to a record here.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .schemas import EvidenceRecord, RunRecord


def new_run_id(stage: str, method: str, task_id: str, rep: int) -> str:
    return f"{stage}:{method}:{task_id}:r{rep}:{uuid.uuid4().hex[:8]}"


class RunLedger:
    """Append-only JSONL store for run records."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: RunRecord) -> None:
        if self.path.exists():
            existing = {json.loads(l)["run_id"] for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()}
            if record.run_id in existing:
                raise ValueError(f"run_id already recorded: {record.run_id}")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


class EvidenceLedger:
    """Append-only EvidenceRecord store; rejects E1 claims dressed as E3/E4."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: EvidenceRecord) -> None:
        if record.evidence_type in ("E3", "E4") and not record.execution_evidence:
            raise ValueError("E3/E4 evidence requires traceable execution evidence")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def unsupported_conclusions(self) -> list[dict]:
        """Conclusions with no evidence record are unsupported by construction."""
        return [r for r in self.read_all() if r.get("conclusion") and not r.get("execution_evidence")]


def append_jsonl(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({**payload, "ts": time.time()}, ensure_ascii=False) + "\n")
