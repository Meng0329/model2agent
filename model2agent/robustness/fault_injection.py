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


def _wrap_predict(src: str, transform: str) -> str:
    """Append a wrapper that transforms incoming `features` for predict/predict_proba.

    This makes semantic faults (schema/drift) ACTUALLY change outputs while keeping the
    module importable — so a clean-oracle comparison can detect them.
    """
    src += (
        "\n\n# --- injected fault wrapper (robustness test) ---\n"
        "_FAULT_TX = lambda features: " + transform + "\n"
        "for _n in ('predict', 'predict_proba', 'predict_class', 'predict_probability'):\n"
        "    if _n in globals():\n"
        "        _o = globals()[_n]\n"
        "        def _w(features=None, *a, _o=_o, **k):\n"
        "            return _o(_FAULT_TX(features), *a, **k)\n"
        "        _w.__name__ = _n\n"
        "        globals()[_n] = _w\n"
    )
    return src


def _apply_fault(copy_dir: Path, fault: str) -> None:
    """Mutate a COPY of the bundle to inject an EFFECTIVE fault (returns silently on no-op)."""
    infer = copy_dir / "infer.py"
    manifest = copy_dir / "manifest.json"
    src = infer.read_text(encoding="utf-8")
    if fault == "missing_dependency":
        infer.write_text("import __nonexistent_dep_xyz__  # injected: missing dependency\n" + src, encoding="utf-8")
    elif fault == "broken_path":
        # actually rename the weights file so loading fails (manifest-only edits are no-ops
        # because infer.py hardcodes its filename)
        m = json.loads(manifest.read_text())
        wp = m.get("weights_path")
        if wp and (copy_dir / wp).exists():
            (copy_dir / wp).rename(copy_dir / (wp + ".moved"))
        m["weights_path"] = wp  # leave manifest pointing at the now-missing file
        manifest.write_text(json.dumps(m), encoding="utf-8")
    elif fault == "deprecated_api":
        import re as _re
        src = _re.sub(r"\btorch\.load\(", "torch.load_removed_api(", src)
        src = _re.sub(r"\bjoblib\.load\(", "joblib.load_removed_api(", src)
        src = _re.sub(r"\.load_model\(", ".load_model_removed_api(", src)
        infer.write_text(src, encoding="utf-8")
    elif fault == "invalid_input_schema":
        # reorder incoming features (silently wrong schema)
        infer.write_text(_wrap_predict(src, "list(reversed(features))"), encoding="utf-8")
    elif fault == "preprocessing_drift":
        # silently change input scaling
        infer.write_text(_wrap_predict(src, "[f * 2.0 for f in features]"), encoding="utf-8")
    elif fault == "weight_config_mismatch":
        # corrupt label ordering / class map if metadata exposes it
        mp = copy_dir / "metrics.json"
        changed = False
        if mp.exists():
            m = json.loads(mp.read_text())
            if isinstance(m.get("classes"), list) and len(m["classes"]) > 1:
                m["classes"] = m["classes"][::-1]; mp.write_text(json.dumps(m)); changed = True
        if not changed:
            # fall back to an effective label-remap wrapper
            infer.write_text(_wrap_predict(src, "features"), encoding="utf-8")
            extra = ("\n\n# injected: label remap\n"
                     "if 'predict' in globals():\n"
                     "    _p0 = globals()['predict']\n"
                     "    globals()['predict'] = lambda features, *a, **k: (_p0(features, *a, **k) + 1) % 10\n")
            infer.write_text(infer.read_text() + extra, encoding="utf-8")


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
                m_res = run_method_m(copy_dir, llm=llm, repair=repair, verify=True, oracle_dir=orig)
                success = bool(m_res.get("success"))
                # Detection: verification (against CLEAN oracle) flags a mismatch, or the
                # import/scan/build fails explicitly.
                checks = m_res.get("steps", {}).get("verification", {}).get("checks", [])
                detected = (m_res.get("steps", {}).get("scan", {}).get("import_error") is not None
                            or m_res.get("steps", {}).get("induction", {}).get("error") is not None
                            or any(c.get("verified") is False for c in checks)
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
