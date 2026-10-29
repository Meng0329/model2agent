"""Baseline B2 — Direct LLM Agent Synthesis (no MCG, no skill routing).

The LLM directly synthesizes a thin Python script that loads the asset's infer module
and answers the request. No Model Capability Graph is built. This isolates the
contribution of AGCI/MCG/structured skill routing.
"""
from __future__ import annotations
import json, textwrap, tempfile, os, sys
from pathlib import Path

from ..llm import LLMClient, unwrap_result
from ..verification.reference_exec import load_infer

SYSTEM = (
    "Write a short Python script that imports the module `infer` from the model bundle "
    "and computes the answer to the user's request, then prints JSON to stdout. Use only "
    "the documented functions. Print exactly one JSON object, no extra text. No imports "
    "beyond `infer`, `json`."
)


def run_task(llm: LLMClient, bundle_dir, card_text: str, functions: list, task, nl_prompt: str) -> dict:
    fn_lines = "\n".join(f"- {f['name']}({', '.join(f['arg_names'])}) -> {f['return_annotation'] or 'any'}: {f['docstring']}"
                         for f in functions if f.get("is_callable"))
    msg = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"MODEL CARD:\n{card_text[:2000]}\n\nFUNCTIONS:\n{fn_lines}\n\nREQUEST: {nl_prompt}"},
    ]
    code = llm.chat(msg, temperature=0.0, max_tokens=700)
    # Extract the python block if wrapped
    if "```" in code:
        code = code.split("```")[1].removeprefix("python").strip()
    bid = str(bundle_dir)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
        f.write(code)
        script_path = f.name
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(bundle_dir) + os.pathsep + env.get("PYTHONPATH", "")
        out = __import__("subprocess").run([sys.executable, script_path], capture_output=True, text=True,
                                           cwd=str(bundle_dir), env=env, timeout=120)
        stdout = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
        try:
            got = unwrap_result(json.loads(stdout))
        except Exception:
            got = {"_raw": stdout[:500]}
        return {"code": code, "got": got, "stderr": out.stderr[:300]}
    except Exception as e:
        return {"code": code, "got": None, "error": f"{type(e).__name__}: {e}"}
    finally:
        Path(script_path).unlink(missing_ok=True)
