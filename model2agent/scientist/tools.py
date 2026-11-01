"""Deterministic MCP tools used by the single-session agents.

Tools only execute or record. They never decide, never hallucinate a value, and
never simulate a measurement: a missing measurement is reported as UNOBSERVABLE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import tool, create_sdk_mcp_server

from .model_introspection import inspect_model
from .schemas import EvidenceRecord, ExperimentPlan, Hypothesis
from .budget import Budget, BudgetExceeded


def _text(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}


# --------------------------------------------------------------------------- #
# Outer Model2Agent builder tools                                            #
# --------------------------------------------------------------------------- #
def make_builder_tools() -> Any:
    @tool("inspect_model",
          "Grounded inspection of a model bundle: real AST functions, real import, "
          "real example execution, weights sha256. Never guesses capabilities.",
          {"bundle_dir": str})
    async def inspect_model_tool(args):
        try:
            facts = inspect_model(args["bundle_dir"])
            return _text({
                "slug": facts.slug, "callable_functions": facts.callable_functions,
                "weights_sha256": facts.weights_sha256, "import_error": facts.import_error,
                "executed_examples": [
                    {"capability": e.capability, "ok": e.ok, "error": e.error,
                     "latency_ms": round(e.latency_ms, 2), "output": e.output}
                    for e in facts.executed_examples
                ],
            })
        except Exception as e:
            return _text({"error": f"{type(e).__name__}: {e}"})

    @tool("execution_check",
          "Independently re-execute the original model (oracle) and strictly compare "
          "the agent's claimed output. Returns ok=false on any mismatch.",
          {"bundle_dir": str, "capability": str, "args_json": str, "output_json": str})
    async def execution_check_tool(args):
        from ..oracle.execution_oracle import ExecutionOracle
        try:
            oracle = ExecutionOracle(args["bundle_dir"])
            payload_args = json.loads(args["args_json"])
            claimed = json.loads(args["output_json"])
            ok, detail = oracle.compare(args["capability"], payload_args, claimed)
            return _text({"ok": ok, **detail})
        except Exception as e:
            return _text({"ok": False, "error": f"{type(e).__name__}: {e}"})

    server = create_sdk_mcp_server("m2a_builder_tools", tools=[inspect_model_tool, execution_check_tool])
    return server


# --------------------------------------------------------------------------- #
# Generated scientist tools                                                  #
# --------------------------------------------------------------------------- #
def make_scientist_tools(*, spec: dict, model_exec: Callable[[str, dict], Any],
                         oracle, ledger, budget: Budget, spec_path: str) -> Any:
    """Tools for the generated Scientist Agent (one main agent + Skills)."""

    @tool("run_model",
          "Execute the scientific model's real inference entry with given args. "
          "Returns the raw model output (evidence type E1).",
          {"capability": str, "args_json": str})
    async def run_model_tool(args):
        budget.tick_model_call(tokens=0, cost_usd=0.0)
        out = model_exec(args["capability"], json.loads(args["args_json"]))
        return _text({"capability": args["capability"], "output": out, "evidence_type": "E1"})

    @tool("query_evidence_oracle",
          "Query a real historical measurement for a candidate. Budget-accounted. "
          "Returns __UNOBSERVABLE__ if no real measurement exists — never a proxy.",
          {"candidate_id": str})
    async def query_oracle_tool(args):
        try:
            value, source = oracle.measure(args["candidate_id"])
        except BudgetExceeded as e:
            return _text({"error": str(e), "budget_exhausted": True})
        return _text({"candidate_id": args["candidate_id"], "measurement": value,
                      "evidence_type": source})

    @tool("plan_experiment",
          "Record a falsifiable experiment plan for a hypothesis.",
          {"hypothesis_id": str, "design": str, "controls": str,
           "observation_metric": str, "refutation_condition": str})
    async def plan_tool(args):
        plan = ExperimentPlan(
            id=f"exp-{budget.experiments + 1}", hypothesis_id=args["hypothesis_id"],
            design=args["design"], controls=[c for c in args["controls"].split(";") if c],
            observation_metric=args["observation_metric"],
            expected_result="", refutation_condition=args["refutation_condition"])
        _append_jsonl(spec_path, {"kind": "experiment", "plan": plan.__dict__})
        return _text({"planned": plan.id})

    @tool("record_evidence",
          "Append one auditable evidence record. evidence_type must be E1/E2/E3/E4; "
          "E3/E4 require traceable execution evidence.",
          {"research_question": str, "hypothesis_id": str, "experiment_id": str,
           "model": str, "input_json": str, "control_variables": str,
           "execution_evidence": str, "observed_json": str, "evidence_type": str,
           "uncertainty": str, "conclusion": str, "limitations": str})
    async def record_tool(args):
        rec = EvidenceRecord(
            id=f"ev-{len(ledger.read_all()) + 1}",
            research_question=args["research_question"], hypothesis_id=args["hypothesis_id"],
            experiment_id=args["experiment_id"], model=args["model"],
            input_data=json.loads(args["input_json"]),
            control_variables=[c for c in args["control_variables"].split(";") if c],
            execution_evidence=args["execution_evidence"],
            observed_result=json.loads(args["observed_json"]),
            evidence_type=args["evidence_type"], uncertainty=args["uncertainty"],
            hypothesis_revision=None, conclusion=args["conclusion"] or None,
            limitations=[l for l in args["limitations"].split(";") if l], timestamp=0.0)
        import time
        rec.timestamp = time.time()
        ledger.append(rec)
        return _text({"recorded": rec.id})

    @tool("revise_hypothesis",
          "Record a hypothesis revision after new evidence.",
          {"hypothesis_id": str, "revision": str, "reason": str})
    async def revise_tool(args):
        _append_jsonl(spec_path, {"kind": "revision", "hypothesis_id": args["hypothesis_id"],
                                  "revision": args["revision"], "reason": args["reason"]})
        return _text({"revised": args["hypothesis_id"]})

    server = create_sdk_mcp_server(
        "m2a_scientist",
        tools=[run_model_tool, query_oracle_tool, plan_tool, record_tool, revise_tool])
    return server


def _append_jsonl(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
