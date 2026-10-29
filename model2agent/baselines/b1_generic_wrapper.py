"""Baseline B1 — Generic Model Wrapper + Agent SDK.

A generic wrapper ignores model-specific semantics: it exposes EVERY discovered function
uniformly (no AGCI semantics, no capability naming, no failure boundaries), then the LLM
routes over that flat function list. Isolates the contribution of model-specific
semantics (related to ablation A5).
"""
from __future__ import annotations
import json

from ..llm import LLMClient
from ..verification.reference_exec import run_reference

SYSTEM = (
    "You are given a list of Python functions from a model bundle. Choose one function and "
    "produce args. Do NOT use any knowledge about what the model is for; rely only on the "
    "function names/signatures. Output ONLY JSON: {\"capability\": <function name>, \"args\": {}}."
)


def run_task(llm: LLMClient, bundle_dir, card_text: str, functions: list, task, nl_prompt: str) -> dict:
    # Generic wrapper: flat function list, NO model card semantics, NO docstrings meaning.
    fn_lines = "\n".join(
        f"- {f['name']}({', '.join(f['arg_names'])})"
        for f in functions if f.get("is_callable") and not f["name"].startswith("_")
    )
    msg = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"FUNCTIONS (names/signatures only):\n{fn_lines}\n\nREQUEST: {nl_prompt}"},
    ]
    from ..llm import extract_json, unwrap_result
    raw = llm.chat(msg, temperature=0.0, max_tokens=2500, json_mode=True)
    plan = extract_json(raw)
    if not isinstance(plan, dict):
        return {"capability": None, "got": None, "error": "parse"}
    try:
        got = unwrap_result(run_reference(bundle_dir, plan["capability"], plan.get("args", {})))
        return {"capability": plan["capability"], "got": got}
    except Exception as e:
        return {"capability": plan.get("capability"), "got": None, "error": f"{type(e).__name__}: {e}"[:200]}
