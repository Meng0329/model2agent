"""Deterministic scaffold: generate a standalone Model Agent project from an
asset bundle. Copies the React+FastAPI template, copies the real weights, and
writes config.json (model info, input type, capabilities, adapters) derived
from the asset's actual manifest + examples — never guessed from the model name.

The main Agent chooses *when* to call this (via the agent-generation skill);
the execution here is deterministic Python (real tool work), per the spec.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from . import config
from .workspace import Workspace

TEMPLATE = config.ROOT / "generated_agent_template"


def _detect_input_type(manifest: dict, examples: dict, capabilities: list) -> str:
    """Infer the natural input type from task_family first, then grounded examples."""
    tf = (manifest.get("task_family") or "").lower()
    if "image" in tf or "vision" in tf:
        return "image"
    if "tabular" in tf or "table" in tf:
        return "tabular"
    if (manifest.get("framework") or "").lower() in ("transformers", "huggingface"):
        return "text"
    # grounded detection from real examples
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            args = recs[0].get("args", {})
            if "image" in args or "image_path" in args or "filepath" in args:
                return "image"
            if "text" in args:
                return "text"
            feats = args.get("features")
            if isinstance(feats, list) and len(feats) > 0:
                return "vector"
            if "data" in args or "X" in args:
                return "tabular"
    return "text"


def _vector_len(examples: dict, capabilities: list) -> int | None:
    """Real feature-vector length from a grounded example, if any."""
    for cap in capabilities:
        recs = examples.get(cap, [])
        if recs:
            feats = recs[0].get("args", {}).get("features")
            if isinstance(feats, list) and len(feats) > 0:
                return len(feats)
    return None


def _feature_names(asset: Path, manifest: dict) -> list[str] | None:
    """Real feature names from metrics.json (tabular) if present."""
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


def _adapter(input_type: str) -> str:
    return {"image": "image", "tabular": "tabular"}.get(input_type, "raw")


def _ensure_web_dist() -> None:
    """The generated Agent is a standalone product — its React UI must be built.
    Build once into the template's web/dist if missing (requires node/npm)."""
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
    """Scaffold the generated agent into Workspace(task_id).project/."""
    _ensure_web_dist()
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
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True, exist_ok=True)
    # copy template (React web build + backend). Skip build deps + caches but
    # KEEP web/dist — the generated Agent is a standalone product with its UI.
    for item in TEMPLATE.rglob("*"):
        if any(part.startswith("node_modules") or part == "__pycache__" for part in item.relative_to(TEMPLATE).parts):
            continue
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

    # class labels for display: explicit > manifest/metrics "labels" > real classes() call > true_label fallback
    labels = []
    def _scalar_labels(v) -> list:
        if isinstance(v, list) and v and all(not isinstance(x, (dict, list)) for x in v):
            return [str(x) for x in v]
        if isinstance(v, dict):
            for k in ("labels", "classes", "result", "target_names"):
                if isinstance(v.get(k), list):
                    return [str(x) for x in v[k] if not isinstance(x, (dict, list))]
        return []
    classes_rec = examples.get("classes")
    if isinstance(classes_rec, list):
        for rec in classes_rec:
            if isinstance(rec, dict) and "result" in rec:
                labels = _scalar_labels(rec["result"])
                if labels:
                    break
        if not labels:
            labels = _scalar_labels(classes_rec)
    if not labels:
        labels = _scalar_labels(manifest.get("labels"))
    if not labels:
        try:
            m = json.loads((asset / "metrics.json").read_text(encoding="utf-8"))
            labels = _scalar_labels(m.get("labels")) or _scalar_labels(m.get("target_names"))
        except Exception:
            pass
    if not labels and "classes" in callable_names:
        # real, deterministic call to the asset's classes() (loads real weights)
        try:
            labels = _scalar_labels(getattr(mod, "classes")())
        except Exception:
            labels = []
    if not labels:
        # fallback: distinct true_label values seen in examples
        seen = []
        for cap in caps:
            for rec in examples.get(cap, []):
                tl = rec.get("true_label")
                if tl is not None and str(tl) not in seen:
                    seen.append(str(tl))
        try:
            seen.sort(key=lambda x: float(x))
        except Exception:
            pass
        labels = seen

    cfg = {
        "slug": slug,
        "model_id": manifest.get("model_id", slug),
        "framework": manifest.get("framework", ""),
        "task_family": manifest.get("task_family", ""),
        "input_type": input_type,
        "adapter": _adapter(input_type),
        "vector_len": _vector_len(examples, caps),
        "feature_names": _feature_names(asset, manifest),
        "labels": labels,
        "capabilities": caps,
        "default_capability": default_cap,
        "capability_map": {c: c for c in caps},
        "asset_dir": f"assets/{slug}",
        "examples": examples,
    }
    (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return proj
