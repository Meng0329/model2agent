"""AGCI — Asset-Grounded Capability Induction.

The scanner introspects a model-asset bundle and produces an *AssetDescriptor*
grounded in executable evidence (real importable functions, real weights, real examples).
Nothing here is hand-written per model — discovery is generic across frameworks.
"""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")


@dataclass
class DiscoveredFunction:
    name: str
    docstring: str
    arg_names: list
    defaults: list
    return_annotation: str
    source_first_line: str
    is_callable: bool


@dataclass
class CapabilityEvidence:
    weights_path: str | None
    weights_sha256: str | None
    metrics: dict
    examples_keys: list
    import_error: str | None


@dataclass
class AssetDescriptor:
    slug: str
    name: str
    framework: str
    task_family: str
    model_id: str
    revision: str
    license: str
    deps: list
    device: str
    card_text: str
    manifest: dict
    functions: list  # list[DiscoveredFunction]
    evidence: dict   # CapabilityEvidence as dict
    bundle_dir: str


def _ast_functions(entry_path: Path) -> list[DiscoveredFunction]:
    src = entry_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            defaults = [ast.dump(d) for d in node.args.defaults]
            ret = ast.unparse(node.returns) if node.returns else ""
            doc = ast.get_docstring(node) or ""
            first_line = (node.body[0].value.value if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) else "")
            out.append(DiscoveredFunction(node.name, doc, args, defaults, ret, first_line, False))
    return out


def _import_entry(bundle_dir: Path, module_name: str) -> Any:
    """Import the asset's native infer module by file path (no sys.path mutation)."""
    entry = bundle_dir / module_name
    spec = importlib.util.spec_from_file_location(f"m2a_asset_{bundle_dir.name}", entry)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_bundle(bundle_dir: str | Path) -> AssetDescriptor:
    bundle_dir = Path(bundle_dir)
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    card = (bundle_dir / manifest.get("card", "model_card.md")).read_text(encoding="utf-8")
    examples = json.loads((bundle_dir / manifest.get("examples", "examples.json")).read_text(encoding="utf-8"))

    # Grounded function discovery via AST (does not trust the manifest's entry_functions list)
    functions = _ast_functions(bundle_dir / manifest["entry_module"])

    # Executable evidence: actually import the entry and confirm callability
    evidence: dict = {"weights_path": None, "weights_sha256": None,
                      "metrics": {}, "examples_keys": list(examples.keys()), "import_error": None}
    try:
        mod = _import_entry(bundle_dir, manifest["entry_module"])
        for fn in functions:
            fn.is_callable = hasattr(mod, fn.name) and callable(getattr(mod, fn.name))
        wp = manifest.get("weights_path")
        if wp:
            wpath = bundle_dir / wp
            evidence["weights_path"] = str(wpath)
            evidence["weights_sha256"] = _sha256(wpath) if wpath.exists() else None
        else:  # HF-style: weights resolved from cache at runtime; record config/tokenizer hash
            cache_root = Path(os.path.expanduser("~/.cache/huggingface/hub"))
            cand = cache_root / f"models--{manifest['model_id'].replace('/','--')}"
            if cand.exists():
                evidence["weights_path"] = str(cand)
                # hash a snapshot config.json if present as a lightweight provenance marker
                cfgs = list(cand.rglob("config.json"))
                if cfgs:
                    evidence["weights_sha256"] = _sha256(cfgs[0])
        metrics_path = bundle_dir / "metrics.json"
        if metrics_path.exists():
            evidence["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception as e:
        evidence["import_error"] = f"{type(e).__name__}: {e}"[:500]

    # Reconcile manifest vs AST: flag discrepancies (a grounded-evidence signal)
    declared = set(manifest.get("entry_functions", []))
    found = {f.name for f in functions}
    evidence["manifest_vs_ast"] = {
        "declared_only": sorted(declared - found),
        "discovered_only": sorted(found - declared),
        "agreed": sorted(declared & found),
    }

    return AssetDescriptor(
        slug=manifest.get("slug", bundle_dir.name), name=manifest["name"],
        framework=manifest["framework"], task_family=manifest["task_family"],
        model_id=manifest["model_id"], revision=manifest.get("revision", ""),
        license=manifest.get("license", ""), deps=manifest.get("deps", []),
        device=manifest.get("device", "cpu"), card_text=card, manifest=manifest,
        functions=[asdict(f) for f in functions], evidence=evidence,
        bundle_dir=str(bundle_dir),
    )
