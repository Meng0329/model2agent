"""Headless entry point for a generated Scientist Agent.

Usage:
  python3 run_research.py --task <task.json> --hidden <hidden_dir> \
      --out <out_dir> --run-id <run_id> [--max-turns N] [--max-budget-usd X]

One main research agent, scientific Skills, real model execution, a budgeted
historical oracle, and an append-only evidence ledger. No subagents.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from m2a_scientist_runtime import model_exec                     # noqa: E402
from m2a_scientist_runtime.store import (                        # noqa: E402
    Budget, Ledger, HistoricalOracleClient,
)
from m2a_scientist_runtime.tools import make_tools              # noqa: E402


def load_scientist() -> dict:
    return json.loads((HERE / "scientist.json").read_text(encoding="utf-8"))


def build_system_prompt(sci: dict) -> str:
    return (
        f"You are {sci.get('name', 'a domain scientist')}, a single autonomous research agent "
        f"built from the scientific model '{sci.get('model_id')}'.\n"
        f"Domain: {sci.get('domain')}. Capabilities: {', '.join(sci.get('capabilities', []))}.\n\n"
        "Operate as a scientist:\n"
        "1. State the research question and what is already known.\n"
        "2. Form falsifiable hypotheses (with a falsifier and a predicted observation).\n"
        "3. Design controlled computational experiments and define metrics.\n"
        "4. Execute the REAL model via run_model — never invent a number.\n"
        "5. Query real historical measurements via query_evidence_oracle within budget.\n"
        "6. Record every observation and conclusion with record_evidence (E1-E4).\n"
        "7. Revise hypotheses when evidence contradicts them.\n"
        "8. Conclude only what the evidence supports; state limitations explicitly.\n\n"
        "Never claim E1 model predictions are E3/E4 measurements. Never fabricate a result. "
        "If the budget is exhausted or a measurement is UNOBSERVABLE, say so."
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--hidden", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--max-budget-usd", type=float, default=2.0)
    args = ap.parse_args()

    task = json.loads(Path(args.task).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sci = load_scientist()

    b = task.get("experimental_budget", {})
    budget = Budget(max_tokens=int(b.get("max_tokens", 2_000_000)),
                    max_model_calls=int(b.get("max_model_calls", 64)),
                    max_experiments=int(b.get("oracle_queries", 32)),
                    max_wall_seconds=float(b.get("max_wall_seconds", 1800)),
                    max_usd=float(b.get("max_usd", 2.0)))
    ledger = Ledger(out / "evidence.jsonl")
    oracle = HistoricalOracleClient(args.hidden, task["hidden_reference"],
                                    out / "oracle_access.jsonl", budget, args.run_id)
    server = make_tools(budget=budget, ledger=ledger, oracle=oracle)

    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage
    opts = ClaudeAgentOptions(
        cwd=str(HERE),
        model=sci.get("agent_model", "deepseek-v4.1-flash"),
        permission_mode="bypassPermissions",
        tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        system_prompt=build_system_prompt(sci),
        mcp_servers={"m2a_scientist": server},
        setting_sources=[],          # isolation: no repo hooks/CLAUDE.md contamination
        max_turns=args.max_turns,
        max_budget_usd=args.max_budget_usd,
        include_partial_messages=True,
    )

    trajectory = []
    t0 = time.perf_counter()
    result = {"run_id": args.run_id, "status": "FAILED", "text": "", "cost_usd": 0.0,
              "num_turns": 0, "session_id": "", "error": None}
    client = ClaudeSDKClient(opts)
    try:
        await client.connect()
        query = (f"{task['scientific_question']}\n\n"
                 f"Candidate input file: {task.get('input_resources', {}).get('candidate_file', 'n/a')}\n"
                 f"Resource budget: {json.dumps(task.get('experimental_budget', {}))}\n"
                 "Record evidence with record_evidence; query real measurements only via "
                 "query_evidence_oracle (budget-accounted). Write your final ranked answer to "
                 'final_selection.json as {"top_ids": [...]}.')
        await client.query(query)
        async for message in client.receive_response():
            trajectory.append({"type": type(message).__name__,
                               "repr": repr(message)[:4000]})
            if isinstance(message, ResultMessage):
                result.update({
                    "status": "OBSERVED" if not getattr(message, "is_error", True) else "FAILED",
                    "text": getattr(message, "result", "") or "",
                    "cost_usd": float(getattr(message, "total_cost_usd", 0.0) or 0.0),
                    "num_turns": int(getattr(message, "num_turns", 0) or 0),
                    "session_id": getattr(message, "session_id", "") or "",
                })
    except Exception as e:  # surfaced in result.json, never hidden
        result["error"] = f"{type(e).__name__}: {e}"
    finally:
        await client.disconnect()

    result["budget"] = budget.as_dict()
    result["latency_s"] = round(time.perf_counter() - t0, 3)
    (out / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in trajectory), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["status"] == "OBSERVED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
