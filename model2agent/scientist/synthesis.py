"""Scientist project scaffolding + verification.

Only infrastructure is copied deterministically (the self-contained runtime).
All scientific content — config, scientist.json, skills, model-specific wiring —
must be authored by the agent from verified facts. Verification fails loudly if
that content is missing or if a real model call does not work.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parent / "runtime"


def scaffold_project(dest: str | Path) -> Path:
    """Create an empty scientist project shell with the runtime library."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(RUNTIME_SRC, dest / "m2a_scientist_runtime",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(RUNTIME_SRC / "run_research.py", dest / "run_research.py")
    (dest / "skills").mkdir(exist_ok=True)
    return dest


def project_ready(dest: str | Path) -> tuple[bool, list[str]]:
    """Check that the agent-authored content exists. Returns (ok, problems)."""
    dest = Path(dest)
    problems = []
    for name in ("config.json", "scientist.json", "run_research.py"):
        if not (dest / name).exists():
            problems.append(f"missing {name}")
    if (dest / "config.json").exists():
        cfg = json.loads((dest / "config.json").read_text(encoding="utf-8"))
        for key in ("slug", "asset_dir", "capabilities", "capability_map", "examples"):
            if key not in cfg:
                problems.append(f"config.json missing key: {key}")
        if not Path(cfg.get("asset_dir", "")).exists() and not (dest / cfg.get("asset_dir", "")).exists():
            problems.append(f"asset_dir does not exist: {cfg.get('asset_dir')}")
    if not any((dest / "skills").glob("*/SKILL.md")):
        problems.append("no scientific skill (skills/*/SKILL.md)")
    return (not problems), problems


def selfcheck(dest: str | Path, timeout: int = 300) -> dict:
    """Run the generated project's real model selfcheck as a subprocess."""
    dest = Path(dest)
    proc = subprocess.run(
        [sys.executable, "-I", str(dest / "m2a_scientist_runtime" / "model_exec.py")],
        capture_output=True, text=True, timeout=timeout, cwd=str(dest))
    if proc.returncode != 0:
        raise RuntimeError(f"selfcheck failed ({proc.returncode}): {proc.stderr[-800:]}")
    return json.loads(proc.stdout)
