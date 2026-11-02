"""Model2Agent — Model-to-Scientist compilation entry point.

ONE single Claude Agent SDK session, MULTIPLE subagents. The main agent decides
everything: which subagent to call, in what order, and how to combine evidence.
There is no fixed pipeline, no stage map, no keyword router, no silent fallback.

Deterministic code here only: scaffold the project shell, expose grounded tools,
run the session, and verify the produced project by real execution.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import config
from .scientist.sdk_session import build_options, run_session, sdk_version
from .scientist.subagents import BUILDER_AGENTS
from .scientist.synthesis import project_ready, scaffold_project, selfcheck
from .scientist.tools import make_builder_tools

_BUILDER_SYSTEM = """You are Model2Agent's Model-to-Scientist compiler, a single session with
specialized subagents. You convert ONE pretrained scientific model into a standalone,
autonomous domain-scientist agent.

Mission (delegate as you see fit; there is no prescribed order):
- Understand the model from REAL evidence (files, imports, executions, weights hash).
- Discover which scientific operations it can really execute.
- Build a capability graph with real dependencies only.
- Author a runnable scientist project in the target directory: one main research agent,
  scientific Skills, and MCP tools run_model / plan_experiment / record_evidence /
  query_evidence_oracle / revise_hypothesis. The project must run headless via run_research.py.
- Independently verify the result.

Non-negotiable rules:
* Never invent capabilities, values, measurements, or scientific facts. Ground every claim.
* If something cannot be verified, report UNVERIFIED and say what would verify it.
* Do NOT simulate results, do not add fallbacks, do not weaken the task.
* The scientist must form falsifiable hypotheses, execute the REAL model, query only
  real historical measurements within budget, revise on contradicting evidence, and
  conclude with explicit limitations. E1 predictions are never reported as E3/E4.
* When you finish, ensure the project passes a real selfcheck (run the model on its
  first real example for every declared capability)."""


def _mission_prompt(bundle_dir: Path, project_dir: Path, task: dict) -> str:
    return (
        "Compile the scientific model in this bundle into a scientist agent.\n"
        f"bundle_dir: {bundle_dir}\n"
        f"project_dir (write the standalone project here): {project_dir}\n"
        f"research task (the scientist must be able to pursue this):\n"
        f"{json.dumps(task, ensure_ascii=False, indent=2)}\n\n"
        "Use the inspect_model and execution_check tools. Write real files. "
        "Finish by running the project's selfcheck and reporting its real output."
    )


async def _run_smsc_async(bundle_dir: Path, task: dict, project_dir: Path,
                          max_turns: int, max_budget_usd: float,
                          agents: dict | None = None,
                          ablation: str | None = None) -> dict:
    scaffold_project(project_dir)
    server = make_builder_tools()
    options = build_options(
        cwd=config.ROOT, agents=agents if agents is not None else BUILDER_AGENTS,
        system_prompt=_BUILDER_SYSTEM,
        mcp_servers={"m2a_builder_tools": server},
        max_turns=max_turns, max_budget_usd=max_budget_usd)
    result = await run_session(_mission_prompt(bundle_dir, project_dir, task), options)

    ready, problems = project_ready(project_dir)
    check = {"ok": False, "error": "project not ready"}
    if ready:
        try:
            check = {"ok": True, "output": selfcheck(project_dir)}
        except Exception as e:  # surfaced, not hidden
            check = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return {
        "method": "M",
        "ablation": ablation,
        "sdk_version": sdk_version(),
        "session": {
            "is_error": result.is_error,
            "stop_reason": result.stop_reason,
            "num_turns": result.num_turns,
            "session_id": result.session_id,
            "cost_usd": result.cost_usd,
            "latency_ms": result.latency_ms,
            "tools": [{"name": t.name, "status": t.status, "is_error": t.is_error}
                      for t in result.tool_events],
        },
        "project": str(project_dir),
        "project_ready": ready,
        "problems": problems,
        "selfcheck": check,
        "success": bool(ready and check.get("ok")),
        "text": result.text,
    }


def run_smsc(bundle_dir: str | Path, task: dict, *, project_dir: str | Path | None = None,
             max_turns: int | None = None, max_budget_usd: float | None = None,
             agents: dict | None = None, ablation: str | None = None) -> dict:
    """Compile one scientific model into a scientist agent (single session, multi-agent).

    ``agents``/``ablation`` exist only for S2 ablations (A9 single-agent compiler,
    A1 no affordance/capability-graph). The default path is unchanged: the full
    BUILDER_AGENTS multi-agent compiler.
    """
    config.assert_secrets()
    bundle_dir = Path(bundle_dir)
    project_dir = Path(project_dir or (config.SCIENTIST_PROJECTS_DIR / bundle_dir.name))
    return asyncio.run(_run_smsc_async(
        bundle_dir, task, project_dir,
        max_turns or config.SCIENTIST_MAX_TURNS,
        max_budget_usd if max_budget_usd is not None else config.SCIENTIST_MAX_BUDGET_USD,
        agents=agents, ablation=ablation))
