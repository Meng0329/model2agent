"""Deterministic execution oracle.

Ground truth comes from executing the ORIGINAL model's native inference entry,
never from the evaluated agent. Comparison is strict and quantitative; the old
"non-empty is good enough" checks for saliency/explain are removed.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..verification.reference_exec import load_infer, run_reference  # reuse the loader


class ExecutionOracle:
    """Re-executes the original model and compares outputs within tolerance."""

    def __init__(self, bundle_dir: str | Path, *, tol_rel: float = 1e-3, tol_abs: float = 1e-6):
        self.bundle_dir = Path(bundle_dir)
        self.tol_rel = tol_rel
        self.tol_abs = tol_abs

    def reference(self, capability: str, args: dict) -> Any:
        return run_reference(self.bundle_dir, capability, args)

    def compare(self, capability: str, args: dict, got: Any) -> tuple[bool, dict]:
        """Compare agent output to a fresh reference execution.

        Returns (ok, detail). Never returns ok=True on an empty/None result.
        """
        if got is None:
            return False, {"reason": "agent returned None"}
        ref = self.reference(capability, args)
        try:
            ok = compare_values(ref, got, self.tol_rel, self.tol_abs)
        except Exception as e:  # malformed structure is a hard mismatch, not a pass
            return False, {"reason": f"compare error: {type(e).__name__}"}
        return ok, {"reference": ref}


def _close(a: float, b: float, tol_rel: float, tol_abs: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= max(tol_abs, tol_rel * max(abs(a), abs(b)))


def compare_values(reference: Any, got: Any, tol_rel: float, tol_abs: float) -> bool:
    """Recursive numeric comparison: scalar, nested dict/list, probability maps."""
    if isinstance(reference, dict) and isinstance(got, dict):
        if set(map(str, reference)) != set(map(str, got)):
            return False
        return all(compare_values(reference[k], got[k], tol_rel, tol_abs) for k in reference)
    if isinstance(reference, (list, tuple)) and isinstance(got, (list, tuple)):
        if len(reference) != len(got):
            return False
        return all(compare_values(r, g, tol_rel, tol_abs) for r, g in zip(reference, got))
    if isinstance(reference, bool) or isinstance(got, bool):
        return reference is got or reference == got
    if isinstance(reference, (int, float)) and isinstance(got, (int, float)):
        return _close(float(reference), float(got), tol_rel, tol_abs)
    if isinstance(reference, str) or isinstance(got, str):
        return str(reference) == str(got)
    return reference is got
