"""Grounded model introspection for the SMSC pipeline.

Facts here come from REAL filesystem + execution observation only: AST function
discovery, an actual import, actually running examples, and a sha256 of weights.
An affordance that cannot be executed is rejected here — never declared.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class IntrospectionError(RuntimeError):
    pass


@dataclass
class ExecutedExample:
    capability: str
    args: dict
    output: Any
    latency_ms: float
    ok: bool
    error: Optional[str] = None


@dataclass
class ModelFacts:
    slug: str
    bundle_dir: str
    manifest: dict
    callable_functions: list[str]
    weights_sha256: Optional[str]
    executed_examples: list[ExecutedExample] = field(default_factory=list)
    import_error: Optional[str] = None

    def real_callables(self) -> list[str]:
        return [f for f in self.callable_functions if not f.startswith("_")]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ast_functions(entry_path: Path) -> list[str]:
    import ast
    tree = ast.parse(entry_path.read_text(encoding="utf-8"))
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]


def load_infer_module(bundle_dir: Path, mod_name: str = "m2a_introspect"):
    """Actually import the asset's infer.py (no path pollution)."""
    entry = bundle_dir / "infer.py"
    if not entry.exists():
        raise IntrospectionError(f"infer.py missing in {bundle_dir}")
    spec = importlib.util.spec_from_file_location(mod_name, entry)
    if spec is None or spec.loader is None:
        raise IntrospectionError(f"cannot create spec for {entry}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def inspect_model(bundle_dir: str | Path, *, run_examples: int = 2) -> ModelFacts:
    """Grounded facts: manifest, AST functions, real import, real example runs."""
    bundle_dir = Path(bundle_dir)
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise IntrospectionError(f"manifest.json missing in {bundle_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slug = manifest.get("slug", bundle_dir.name)

    ast_fns = _ast_functions(bundle_dir / "infer.py")
    weights_path = manifest.get("weights_path")
    sha = None
    if weights_path:
        wp = bundle_dir / weights_path
        if wp.exists():
            sha = sha256_file(wp)

    mod = None
    import_error = None
    try:
        mod = load_infer_module(bundle_dir)
    except Exception as e:  # noqa: BLE001 — recorded, surfaced to caller as facts.import_error
        import_error = f"{type(e).__name__}: {e}"[:300]

    examples_path = bundle_dir / "examples.json"
    examples = {}
    if examples_path.exists():
        examples = json.loads(examples_path.read_text(encoding="utf-8"))

    executed: list[ExecutedExample] = []
    if mod is not None:
        for cap, exs in examples.items():
            fn = getattr(mod, cap, None)
            if not callable(fn):
                continue
            for ex in exs[:run_examples]:
                args = ex.get("args", {})
                t0 = time.perf_counter()
                try:
                    out = fn(**args)
                    executed.append(ExecutedExample(cap, args, out,
                                                    (time.perf_counter() - t0) * 1000, True))
                except Exception as e:  # noqa: BLE001 — real error, not silent
                    executed.append(ExecutedExample(cap, args, None,
                                                    (time.perf_counter() - t0) * 1000, False,
                                                    f"{type(e).__name__}: {e}"[:300]))

    return ModelFacts(
        slug=slug, bundle_dir=str(bundle_dir), manifest=manifest,
        callable_functions=ast_fns, weights_sha256=sha,
        executed_examples=executed, import_error=import_error,
    )


def require_grounded_affordance(facts: ModelFacts, capability: str, entry: str) -> bool:
    """An affordance is grounded iff its entry is a real callable that ran ok."""
    if capability not in facts.real_callables():
        return False
    mod_ok = facts.import_error is None
    ran_ok = any(e.capability == capability and e.ok for e in facts.executed_examples)
    return mod_ok and ran_ok
