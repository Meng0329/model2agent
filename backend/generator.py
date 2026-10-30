"""Deterministic scaffold: generate a standalone Model Agent project from an
asset bundle. Copies the model-agnostic template, copies the real weights, and
writes config.json (model info, input type, capabilities) derived from the
asset's actual manifest + examples — never guessed from the model name.

The main Agent chooses *when* to call this (via the agent-generation skill);
the execution here is deterministic Python (real tool work), per the spec.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from . import config
from .workspace import Workspace

TEMPLATE = Path(__file__).resolve().parent / "templates" / "generated_agent"


def _detect_input_type(manifest: dict, examples: dict, capabilities: list) -> str:
    """Infer the direct-prediction input type from grounded examples."""
    # Grounded detection from real examples first (never from the model name).
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            args = recs[0].get("args", {})
            feats = args.get("features")
            if isinstance(feats, list) and len(feats) > 0:
                return "vector64" if len(feats) == 64 else "vector"
            if "image" in args or "image_path" in args or "filepath" in args:
                return "image"
            if "text" in args:
                return "text"
            if "data" in args or "X" in args:
                return "tabular"
    tf = (manifest.get("task_family") or "").lower()
    if "image" in tf or "vision" in tf:
        return "image"
    return "tabular"


def _vector_len(examples: dict, capabilities: list) -> int | None:
    """Real feature-vector length from a grounded example, if any."""
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            feats = recs[0].get("args", {}).get("features")
            if isinstance(feats, list) and len(feats) > 0:
                return len(feats)
    return None


def generate(task_id: str, asset_dir: str | Path) -> Path:
    """Scaffold the generated agent into Workspace(task_id).project/."""
    asset = Path(asset_dir)
    manifest = json.loads((asset / "manifest.json").read_text(encoding="utf-8"))
    ex_file = manifest.get("examples", "examples.json")
    examples = json.loads((asset / ex_file).read_text(encoding="utf-8"))

    # capabilities = public, REAL callables in infer.py that have an example
    callable_names = set()
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("m2a_gen_cap_" + (manifest.get("slug") or asset.name),
                                            str(asset / manifest.get("entry_module", "infer.py")))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        callable_names = {n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))}
    except Exception:
        callable_names = {f["name"] for f in manifest.get("functions", []) if f.get("is_callable")}
    funcs = [n for n in examples.keys() if n in callable_names]
    if not funcs:
        funcs = [f["name"] for f in manifest.get("functions", []) if f.get("is_callable") and not f["name"].startswith("_")]

    caps = funcs
    default_cap = caps[0] if caps else ""
    input_type = _detect_input_type(manifest, examples, caps)

    ws = Workspace(task_id)
    proj = ws.project
    # start from a clean project (only the scaffold, not stale agent scratch)
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True, exist_ok=True)
    # copy template
    for item in TEMPLATE.rglob("*"):
        rel = item.relative_to(TEMPLATE)
        dst = proj / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)
    # copy real asset into project/assets/<slug>/
    slug = manifest.get("slug") or asset.name
    asset_dst = proj / "assets" / slug
    shutil.copytree(asset, asset_dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    cfg = {
        "slug": slug,
        "model_id": manifest.get("model_id", slug),
        "framework": manifest.get("framework", ""),
        "task_family": manifest.get("task_family", ""),
        "input_type": input_type,
        "vector_len": _vector_len(examples, caps),
        "capabilities": caps,
        "default_capability": default_cap,
        "capability_map": {c: c for c in caps},
        "asset_dir": f"assets/{slug}",
        "examples": examples,
    }
    (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return proj
