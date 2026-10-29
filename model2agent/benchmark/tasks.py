"""Frozen benchmark task schema (aligned to Paper2Agent: tutorial / novel / open-ended)."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Task:
    task_id: str
    slug: str
    split: str            # "tutorial" | "novel" | "open_ended"
    capability: str
    args: dict
    reference_output: object  # produced by original-model execution (ground truth)
    check: str = "exact"      # "exact" | "proba" | "explain" | "saliency"
    nl_prompt: str = ""       # natural-language rendering of the task (for NL methods)

    def to_dict(self):
        return asdict(self)


def load_tasks(path) -> list[Task]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task(**t) for t in data["tasks"]]


def save_tasks(tasks: list[Task], path) -> None:
    Path(path).write_text(json.dumps(
        {"frozen": True, "n": len(tasks), "tasks": [t.to_dict() for t in tasks]},
        ensure_ascii=False, indent=2), encoding="utf-8")
