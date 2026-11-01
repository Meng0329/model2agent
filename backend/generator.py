"""Deterministic scaffold: generate a standalone Model Agent project from an asset bundle.

This module is a thin scaffolder: it copies the React+FastAPI template, copies the
real weights, and writes config.json + agent_ui.json from ASSERTED asset facts
(manifest/examples) plus a single real call to the asset's classes(). It does not
guess, infer, or fall back. Anything the asset does not declare is left absent, so
the runtime can surface it honestly.

The outer Model2Agent agent owns the per-model input experience and may rewrite
agent_ui.json / adapters.py; this file only seeds them from the asset.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from . import config
from .workspace import Workspace

TEMPLATE = config.ROOT / "generated_agent_template"


def _load_module(asset: Path, manifest: dict):
    """Import the asset's infer.py exactly once and return the live module."""
    import importlib.util as _ilu
    mod_path = asset / manifest.get("entry_module", "infer.py")
    spec = _ilu.spec_from_file_location(
        "m2a_gen_cap_" + (manifest.get("slug") or asset.name), str(mod_path))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_callables(mod) -> set[str]:
    return {n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))}


def _vector_len(examples: dict, capabilities: list) -> int | None:
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            feats = recs[0].get("args", {}).get("features")
            if isinstance(feats, list) and len(feats) > 0:
                return len(feats)
    return None


def _feature_names(asset: Path) -> list[str] | None:
    m = asset / "metrics.json"
    if m.exists():
        try:
            j = json.loads(m.read_text(encoding="utf-8"))
            names = j.get("feature_names")
            if isinstance(names, list) and names:
                return [str(n) for n in names]
        except Exception:
            pass
    return None


def _labels_from_asset(asset: Path, manifest: dict, mod) -> list[str]:
    """Labels must be real. Prefer manifest labels, then metrics, then classes()."""
    def scalar(v):
        if isinstance(v, list) and v and all(not isinstance(x, (dict, list)) for x in v):
            return [str(x) for x in v]
        return []

    labels = scalar(manifest.get("labels"))
    if labels:
        return labels
    m = asset / "metrics.json"
    if m.exists():
        try:
            j = json.loads(m.read_text(encoding="utf-8"))
            labels = scalar(j.get("labels")) or scalar(j.get("target_names"))
        except Exception:
            labels = []
    if labels:
        return labels
    if hasattr(mod, "classes"):
        labels = scalar(mod.classes())
        if labels:
            return labels
    raise RuntimeError(
        "cannot determine class labels: asset declares none and classes() returned none")


def _input_type(manifest: dict) -> str:
    it = manifest.get("input_type")
    if not it:
        raise RuntimeError("manifest.input_type is required (no inference fallback)")
    return str(it)


def _input_spec(input_type: str, examples: dict, capabilities: list,
                vector_len: int | None, feature_names: list[str] | None) -> dict:
    sample = None
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            feats = recs[0].get("args", {}).get("features")
            if isinstance(feats, list):
                sample = feats
                break
    if input_type == "image":
        return {"mode": "image", "accept": "image/*", "paste": True}
    if input_type == "tabular":
        return {"mode": "tabular", "accept": ".csv,text/csv",
                "feature_names": feature_names, "sample": sample}
    if input_type == "text":
        return {"mode": "text", "multiline": True}
    if input_type == "vector":
        return {"mode": "vector", "dim": vector_len, "sample": sample}
    return {"mode": input_type}


def _ensure_web_dist() -> None:
    """The generated Agent is a standalone product; its React UI must be built."""
    dist = TEMPLATE / "web" / "dist"
    if (dist / "index.html").exists():
        return
    import subprocess
    web = TEMPLATE / "web"
    subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=str(web), check=True, timeout=600)
    subprocess.run(["npm", "run", "build"], cwd=str(web), check=True, timeout=600)
    if not (dist / "index.html").exists():
        raise RuntimeError("web build did not produce web/dist/index.html")


def generate(task_id: str, asset_dir: str | Path) -> Path:
    _ensure_web_dist()
    asset = Path(asset_dir)
    manifest = json.loads((asset / "manifest.json").read_text(encoding="utf-8"))
    examples = json.loads((asset / manifest.get("examples", "examples.json")).read_text(encoding="utf-8"))

    mod = _load_module(asset, manifest)
    callables = _real_callables(mod)
    caps = [n for n in examples.keys() if n in callables]
    if not caps:
        raise RuntimeError("no capability with both a real callable and an example")

    slug = manifest.get("slug") or asset.name
    input_type = _input_type(manifest)
    vector_len = _vector_len(examples, caps)
    feature_names = _feature_names(asset)
    labels = _labels_from_asset(asset, manifest, mod)

    image_cfg = None
    if input_type == "image":
        image_cfg = manifest.get("image")
        if not isinstance(image_cfg, dict) or not image_cfg:
            raise RuntimeError("image asset must declare manifest.image (no heuristic polarity)")

    presets = manifest.get("preset_questions")
    if presets is not None and (not isinstance(presets, list) or len(presets) != 3):
        raise RuntimeError("manifest.preset_questions must contain exactly 3 questions")

    ws = Workspace(task_id)
    proj = ws.project
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True, exist_ok=True)
    for item in TEMPLATE.rglob("*"):
        if any(part.startswith("node_modules") or part == "__pycache__"
               for part in item.relative_to(TEMPLATE).parts):
            continue
        rel = item.relative_to(TEMPLATE)
        dst = proj / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)

    asset_dst = proj / "assets" / slug
    shutil.copytree(asset, asset_dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    cfg = {
        "slug": slug,
        "model_id": manifest.get("model_id", slug),
        "framework": manifest.get("framework", ""),
        "task_family": manifest.get("task_family", ""),
        "input_type": input_type,
        "adapter": input_type,
        "vector_len": vector_len,
        "feature_names": feature_names,
        "labels": labels,
        "capabilities": caps,
        "default_capability": caps[0],
        "capability_map": {c: c for c in caps},
        "asset_dir": f"assets/{slug}",
        "examples": examples,
    }
    if image_cfg is not None:
        cfg["image_preprocess"] = image_cfg
    (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    ui = {
        "model": {
            "slug": slug, "framework": manifest.get("framework", ""),
            "input_type": input_type, "labels": labels,
            "capabilities": caps, "vector_len": vector_len,
            "feature_names": feature_names,
        },
        "input": _input_spec(input_type, examples, caps, vector_len, feature_names),
        "presets": presets or [],
        "pipeline": ["input", "preprocess", "features", "inference", "result"],
        "result_views": [c for c in ("predict", "predict_proba", "saliency", "explain", "classes") if c in caps],
    }
    (proj / "agent_ui.json").write_text(json.dumps(ui, ensure_ascii=False, indent=2), encoding="utf-8")
    return proj
