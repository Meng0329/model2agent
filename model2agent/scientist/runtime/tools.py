"""Scientist MCP tools (self-contained, deterministic, no simulation)."""
from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server

from . import model_exec
from .store import Budget, BudgetExceeded, Ledger, HistoricalOracleClient, UNOBSERVABLE


def _text(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}


def make_tools(*, budget: Budget, ledger: Ledger, oracle: HistoricalOracleClient):
    @tool("run_model", "Run the real scientific model. Evidence type E1.",
          {"capability": str, "args_json": str})
    async def run_model_tool(args):
        budget.tick_model_call()
        try:
            out = model_exec.run(args["capability"], json.loads(args["args_json"]))
            return _text({"capability": args["capability"], "output": out, "evidence_type": "E1"})
        except Exception as e:
            return _text({"error": f"{type(e).__name__}: {e}", "is_error": True})

    @tool("query_evidence_oracle",
          "Query a real historical measurement (budget-accounted). UNOBSERVABLE if none.",
          {"candidate_id": str})
    async def query_tool(args):
        try:
            value = oracle.measure(args["candidate_id"])
        except BudgetExceeded as e:
            return _text({"error": str(e), "budget_exhausted": True})
        return _text({"candidate_id": args["candidate_id"], "measurement": value,
                      "evidence_type": "E3"})

    @tool("record_evidence", "Append an auditable evidence record (E1-E4).",
          {"record_json": str})
    async def record_tool(args):
        rec = json.loads(args["record_json"])
        rid = ledger.append(rec)
        return _text({"recorded": rid})

    @tool("revise_hypothesis",
          "Record a hypothesis revision after new evidence (appends revisions.jsonl).",
          {"hypothesis_id": str, "revision": str, "reason": str})
    async def revise_tool(args):
        import json as _json
        import time as _time
        out = ledger.path.parent / "revisions.jsonl"
        with open(out, "a", encoding="utf-8") as f:
            f.write(_json.dumps({"hypothesis_id": args["hypothesis_id"],
                                 "revision": args["revision"], "reason": args["reason"],
                                 "ts": _time.time()}, ensure_ascii=False) + "\n")
        return _text({"revised": args["hypothesis_id"]})

    server = create_sdk_mcp_server("m2a_scientist",
                                   tools=[run_model_tool, query_tool, record_tool, revise_tool])
    return server
