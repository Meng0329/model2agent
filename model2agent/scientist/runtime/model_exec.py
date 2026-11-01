"""Model executor for a generated scientist project.

Loads the asset's native infer.py and exposes only the real callables.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE.parent / "config.json").read_text(encoding="utf-8"))
ASSET = Path(CFG["asset_dir"])
if not ASSET.is_absolute():
    ASSET = (HERE.parent / ASSET).resolve()

_mod = None


def _load():
    global _mod
    if _mod is not None:
        return _mod
    entry = ASSET / "infer.py"
    if not entry.exists():
        raise FileNotFoundError(f"infer.py missing: {entry}")
    spec = importlib.util.spec_from_file_location(f"m2a_sci_infer_{CFG.get('slug', 'asset')}", entry)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create import spec for {entry}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    _mod = mod
    return mod


def list_capabilities() -> list[str]:
    return list(CFG.get("capabilities", []))


def run(capability: str, args: dict):
    """Execute a real model capability. Unknown capability is a hard error."""
    capmap = CFG.get("capability_map", {})
    entry = capmap.get(capability, capability)
    fn = getattr(_load(), entry, None)
    if not callable(fn):
        raise AttributeError(f"capability {capability!r} -> {entry!r} is not callable")
    return fn(**args)


def selfcheck() -> dict:
    """Run the first real example of every declared capability."""
    out = {}
    examples = CFG.get("examples", {})
    for cap in list_capabilities():
        exs = examples.get(cap, [])
        if not exs:
            out[cap] = {"ok": False, "error": "no example"}
            continue
        try:
            out[cap] = {"ok": True, "output": run(cap, exs[0].get("args", {}))}
        except Exception as e:  # surfaced, never hidden
            out[cap] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return out


if __name__ == "__main__":
    print(json.dumps(selfcheck(), ensure_ascii=False, default=str))
