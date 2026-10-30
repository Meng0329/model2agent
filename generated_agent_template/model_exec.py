"""Real model execution for the generated Agent. Loads the asset's native
infer.py and exposes each discovered capability. Never fabricates outputs."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ASSET = HERE / CFG["asset_dir"]
_spec = importlib.util.spec_from_file_location("m2a_gen_infer_" + CFG["slug"], str(ASSET / "infer.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def list_capabilities():
    return CFG["capabilities"]


def run(capability: str, args: dict | None = None):
    entry = CFG["capability_map"].get(capability, capability)
    fn = getattr(_mod, entry)
    return fn(**(args or {}))


def selfcheck() -> dict:
    ex = CFG.get("examples", {})
    out = {}
    for c in CFG["capabilities"]:
        recs = ex.get(c, [])
        if recs:
            out[c] = run(c, recs[0].get("args", {}))
    return out


if __name__ == "__main__":
    print(json.dumps(selfcheck(), ensure_ascii=False, default=str))
