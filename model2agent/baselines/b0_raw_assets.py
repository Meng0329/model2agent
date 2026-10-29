"""Baseline B0 — DeepSeek + Raw Model Assets (strongest baseline; Claude+Repo analogue).

The LLM is given the FULL raw asset (native infer.py source + model card + examples)
and the request, and may synthesize + execute a Python snippet against the real model.
No induced capability graph, no structured routing, no verification/repair loop.
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path

from ..llm import LLMClient, unwrap_result

SYSTEM = (
    "You are given a trained model's full native inference source (infer.py), its model card, "
    "and examples. Write a short Python script that imports `infer` from the current directory, "
    "calls the appropriate function on the requested input, and prints exactly one JSON value "
    "to stdout. No prose, no markdown fences."
)


def run_task(llm: LLMClient, bundle_dir, card_text: str, functions: list, task, nl_prompt: str) -> dict:
    bundle_dir = Path(bundle_dir)
    source = (bundle_dir / "infer.py").read_text(encoding="utf-8")
    msg = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": (
            f"MODEL CARD:\n{card_text[:1500]}\n\ninfer.py SOURCE:\n{source[:4000]}\n\n"
            f"REQUEST: {nl_prompt}\nWrite the script.")},
    ]
    code = llm.chat(msg, temperature=0.0, max_tokens=700)
    if "```" in code:
        code = code.split("```")[1].removeprefix("python").strip()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
        f.write(code); script_path = f.name
    try:
        env = dict(os.environ); env["PYTHONPATH"] = str(bundle_dir) + os.pathsep + env.get("PYTHONPATH", "")
        out = subprocess.run([sys.executable, script_path], capture_output=True, text=True,
                             cwd=str(bundle_dir), env=env, timeout=120)
        stdout = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
        try:
            got = unwrap_result(json.loads(stdout))
        except Exception:
            got = {"_raw": stdout[:400]}
        return {"code": code, "got": got, "stderr": out.stderr[:300]}
    except Exception as e:
        return {"code": code, "got": None, "error": f"{type(e).__name__}: {e}"}
    finally:
        Path(script_path).unlink(missing_ok=True)
