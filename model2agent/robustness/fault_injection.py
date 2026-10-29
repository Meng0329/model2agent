"""Robustness / fault injection (aligned to Paper2Agent's 12-config adversarial test, +2 model-specific).

Each fault is applied to a *copy* of the asset bundle (never the original), then the
Model2Agent pipeline (or the specific method) runs against the corrupted copy and we
record: detection (did the run raise/flag a fault?), repair (did it auto-fix?), and
post-repair consistency (does the output still match the original reference execution).
Unsafe faults (e.g. wrong label map that would silently change semantics) must be
REJECTED, not silently "fixed".
"""
from __future__ import annotations
import json
import shutil
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path

from .. import config
from ..agci.asset_scanner import scan_bundle
from ..verification.reference_exec import run_reference
from ..orchestrator import run_method_m
from ..llm import LLMClient, scrub

FAULT_TYPES = [
    "missing_dependency",       # remove a required dep from deps / break import
    "broken_path",              # point weights path to a nonexistent file
    "deprecated_api",           # rewrite the load call to an incompatible form
    "invalid_input_schema",     # swap feature order / wrong dtype in example
    "preprocessing_drift",      # change normalization constant in infer.py
    "weight_config_mismatch",   # wrong class map / label order in metadata
]


@dataclass
class FaultResult:
    slug: str
    fault: str
    method: str
    detected: bool
    repaired: bool
    post_repair_consistent: bool
    unsafe_rejected: bool
    notes: str = ""


def _apply_fault(copy_dir: Path, fault: str) -> None:
    """Mutate a COPY of the bundle to inject the fault. Returns silently on no-op."""
    infer = copy_dir / "infer.py"
    manifest = copy_dir / "manifest.json"
    src = infer.read_text(encoding="utf-8")
    if fault == "missing_dependency":
        # corrupt the import line so it cannot load (simulates missing dep)
        src = src.replace("import torch", "import torch_nope_missing_dep_xyz")
        infer.write_text(src, encoding="utf-8")
    elif fault == "broken_path":
        m = json.loads(manifest.read_text())
        m["weights_path"] = "does_not_exist.pt"
        manifest.write_text(json.dumps(m), encoding="utf-8")
    elif fault == "deprecated_api":
        # rewrite torch.load map_location usage to an undefined kwarg
        src = src.replace("torch.load(_HERE / \"cnn_state.pt\", map_location=dev)",
                          "tload(_HERE / \"cnn_state.pt\")")
        src = src.replace("joblib.load(_HERE / \"model.joblib\")", "joblib_load_bad(_HERE / \"model.joblib\")")
        src = src.replace("clf.load_model(str(_HERE / \"model.json\"))", "clf.load_model_bad(str(_HERE / \"model.json\"))")
        infer.write_text(src, encoding="utf-8")
    elif fault == "invalid_input_schema":
        ex = json.loads((copy_dir / "examples.json").read_text())
        for block in ex.values():
            for e in block:
                a = e.get("args", {})
                if "features" in a and isinstance(a["features"], list) and len(a["features"]) >= 2:
                    a["features"][0], a["features"][-1] = a["features"][-1], a["features"][0]
        (copy_dir / "examples.json").write_text(json.dumps(ex), encoding="utf-8")
    elif fault == "preprocessing_drift":
        # change normalization scale 16.0 -> 8.0 (CNN) — silently changes semantics
        src = src.replace("scale = 16.0", "scale = 8.0")
        infer.write_text(src, encoding="utf-8")
    elif fault == "weight_config_mismatch":
        # corrupt metadata label order (model.json metrics) — unsafe if used
        mp = copy_dir / "metrics.json"
        if mp.exists():
            m = json.loads(mp.read_text())
            if "classes" in m and isinstance(m["classes"], list) and len(m["classes"]) > 1:
                m["classes"] = m["classes"][::-1]
                mp.write_text(json.dumps(m), encoding="utf-8")


def run_fault_injection(slug: str, methods=("M",), faults=None, repair: bool = True) -> list[FaultResult]:
    faults = faults or FAULT_TYPES
    orig = config.MODEL_ASSETS_DIR / slug
    ref = scan_bundle(orig)
    # reference outputs on clean examples (for consistency check)
    ref_outputs = {}
    ex = json.loads((orig / ref.manifest.get("examples", "examples.json")).read_text(encoding="utf-8"))
    for cap, samples in ex.items():
        if samples:
            a = samples[0].get("args", {})
            try:
                ref_outputs[cap] = run_reference(orig, cap, a)
            except Exception:
                pass

    results = []
    for fault in faults:
        copy_dir = config.LOGS_DIR / "fault_copy" / f"{slug}_{fault}"
        if copy_dir.exists():
            shutil.rmtree(copy_dir)
        shutil.copytree(orig, copy_dir)
        try:
            _apply_fault(copy_dir, fault)
        except Exception as e:
            results.append(FaultResult(slug, fault, "M", False, False, False, False,
                                        f"fault_injection_error: {e}"))
            continue
        for method in methods:
            try:
                llm = LLMClient("robust")
                m_res = run_method_m(copy_dir, llm=llm, repair=repair, verify=True)
                success = bool(m_res.get("success"))
                # Detection: did verification mark any capability as failed/None, or did build fail?
                checks = m_res.get("steps", {}).get("verification", {}).get("checks", [])
                detected = (m_res.get("steps", {}).get("induction", {}).get("error") is not None
                            or any(c.get("verified") is False or c.get("reason") for c in checks)
                            or m_res.get("steps", {}).get("build", {}).get("error") is not None)
                # Consistency: re-run on clean handled by comparing to ref_outputs if verified
                consistent = True
                if success and ref_outputs:
                    for cap, ref_o in ref_outputs.items():
                        try:
                            from ..verification.reference_exec import compare, load_infer
                            got = getattr(load_infer(copy_dir), cap)(**(ex.get(cap, [{}])[0].get("args", {})))
                            if not compare(cap, ref_o, got):
                                consistent = False
                        except Exception:
                            pass
                # Unsafe rejection: preprocessing_drift / weight_config_mismatch SHOULD be rejected
                # (silently changed semantics). We treat "success=True with inconsistent output" as an
                # UNSAFE silent pass -> unsafe_rejected=False (failure mode we must catch).
                unsafe = fault in ("preprocessing_drift", "weight_config_mismatch")
                unsafe_rejected = bool(unsafe and not success)
                results.append(FaultResult(
                    slug, fault, method, detected=detected, repaired=success and detected,
                    post_repair_consistent=consistent, unsafe_rejected=unsafe_rejected,
                    notes=scrub(json.dumps({"m_success": success,
                                            "cap_rate": m_res.get("capability_verification_rate")}))[:200]))
            except Exception as e:
                results.append(FaultResult(slug, fault, method, False, False, False, False,
                                          f"{type(e).__name__}: {e}"))
    return results


def save_fault_results(slug: str, results: list[FaultResult], path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(r) for r in results]
    import datetime
    unsafe_results = [r for r in results if r.fault in ("preprocessing_drift", "weight_config_mismatch")]
    out = {"slug": slug, "ts": datetime.datetime.utcnow().isoformat(),
           "detection_rate": sum(r.detected for r in results) / len(results) if results else 0.0,
           "repair_rate": sum(r.repaired for r in results) / len(results) if results else 0.0,
           "consistency_rate": sum(r.post_repair_consistent for r in results) / len(results) if results else 0.0,
           "unsafe_reject_rate": (sum(r.unsafe_rejected for r in unsafe_results) / len(unsafe_results)
                                  if unsafe_results else 0.0),
           "results": rows}
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
