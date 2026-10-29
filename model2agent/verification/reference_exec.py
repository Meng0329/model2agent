"""Reference execution — the ground-truth oracle.

Ground truth for every benchmark task comes from executing the ORIGINAL model's
native inference entry (never from the evaluated agent itself). Also provides
behavioral-fidelity comparison between a method's output and reference execution.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Any


_result_cache: dict = {}


def load_infer(bundle_dir: str | Path):
    """Import the asset's native infer module by path (cached per bundle)."""
    bundle_dir = Path(bundle_dir)
    key = str(bundle_dir)
    if key in _result_cache:
        return _result_cache[key]
    spec = importlib.util.spec_from_file_location(f"m2a_ref_{bundle_dir.name}", bundle_dir / "infer.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore
    _result_cache[key] = mod
    return mod


def run_reference(bundle_dir: str | Path, capability: str, args: dict) -> Any:
    """Execute a capability on the real model to produce reference output."""
    mod = load_infer(bundle_dir)
    fn = getattr(mod, capability)
    return fn(**args)


def _as_scalar(x):
    if isinstance(x, dict) and "value" in x and len(x) == 1:
        return x["value"]
    return x


def compare_exact(reference: Any, got: Any) -> bool:
    """Exact match for scalar predictions (int/str/bool)."""
    return _as_scalar(reference) == _as_scalar(got)


def compare_proba(reference: dict, got: dict, tol: float = 1e-6) -> bool:
    """Probability-vector match within tolerance (keys may be str/int)."""
    if not isinstance(reference, dict) or not isinstance(got, dict):
        return False
    if set(map(str, reference)) != set(map(str, got)):
        return False
    return all(abs(float(reference[k]) - float(got[k])) <= tol for k in reference)


def compare(capability: str, reference: Any, got: Any) -> bool:
    if capability in ("predict_proba",):
        return compare_proba(reference, got)
    if capability == "explain":
        # structural: first row's feature label should match
        try:
            return reference and got and reference[0].get("feature") == got[0].get("feature")
        except Exception:
            return False
    if capability == "saliency":
        return bool(reference) and bool(got)
    return compare_exact(reference, got)
