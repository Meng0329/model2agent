"""Model2Agent Orchestrator (single, monolithic). Method M.

Pipeline: AGCI scan -> capability induction -> MCG -> uniform agent build ->
reference-execution verification + repair loop. Returns a structured result the
runner persists as raw JSONL for the statistical layer.
"""
from __future__ import annotations
import json
import traceback
from pathlib import Path

from . import config
from .agci.asset_scanner import scan_bundle
from .agci.capability_inducer import induce_capabilities
from .mcg.graph import build_mcg, save_mcg
from .builder.agent_builder import build_agent
from .verification.reference_exec import run_reference, load_infer, compare
from .llm import LLMClient, scrub


def run_method_m(bundle_dir, *, llm=None, repair: bool = True, verify: bool = True, build: bool = True):
    """Full Model2Agent conversion of one asset. Returns a structured dict (success + evidence)."""
    bundle_dir = Path(bundle_dir)
    llm = llm or LLMClient("M")
    res = {"method": "M", "slug": bundle_dir.name, "steps": {}, "success": False}

    # 1. AGCI scan (asset-grounded, no LLM)
    try:
        desc = scan_bundle(bundle_dir)
        res["steps"]["scan"] = {
            "framework": desc.framework, "task_family": desc.task_family,
            "functions": [f["name"] for f in desc.functions if f.get("is_callable")],
            "weights_sha256": (desc.evidence.get("weights_sha256") or "")[:32],
            "import_error": desc.evidence.get("import_error"),
            "ast_vs_manifest": desc.evidence.get("manifest_vs_ast"),
        }
        res["descriptor"] = {k: getattr(desc, k) for k in ("slug", "name", "framework", "task_family", "model_id", "revision", "license")}
    except Exception as e:
        res["steps"]["scan"] = {"error": f"{type(e).__name__}: {e}"}
        return res

    if desc.evidence.get("import_error"):
        res["steps"]["scan_error"] = desc.evidence["import_error"]
        return res

    # 2. Capability induction (LLM, grounded in discovered functions)
    try:
        caps = induce_capabilities(desc, llm)
        res["steps"]["induction"] = {
            "n_capabilities": len(caps),
            "capabilities": [{"name": c.name, "entry": c.entry_function, "depends_on": c.depends_on} for c in caps],
        }
    except Exception as e:
        res["steps"]["induction"] = {"error": f"{type(e).__name__}: {e}"}
        res["steps"]["induction_error"] = scrub(f"{traceback.format_exc()}"[:500])
        return res

    # 3. MCG
    mcg = build_mcg(desc.slug, caps)
    (config.GENERATED_AGENTS_DIR / desc.slug).mkdir(parents=True, exist_ok=True)
    save_mcg(mcg, config.GENERATED_AGENTS_DIR / desc.slug / "mcg.json")
    res["steps"]["mcg"] = {"nodes": len(mcg.nodes), "edges": len(mcg.edges),
                           "root_capabilities": mcg.root_capabilities}

    # 4. Build standalone agent (uniform template)
    if build:
        try:
            out = build_agent(desc, mcg)
            res["steps"]["build"] = {"agent_dir": str(out), "module": "agent.py"}
        except Exception as e:
            res["steps"]["build"] = {"error": f"{type(e).__name__}: {e}"}
            if not repair:
                return res

    # 5. Verification against reference execution (real weights)
    if verify:
        verified = 0
        checks = []
        unverified = []
        mod = load_infer(bundle_dir)
        import json as _j
        examples = _j.loads(Path(bundle_dir).joinpath(desc.manifest.get("examples", "examples.json")).read_text(encoding="utf-8"))
        for c in caps:
            # Only capabilities with a grounded example are *verifiable*; the rest are
            # recorded as unverified (not counted as failures).
            ex = examples.get(c.entry_function)
            if not ex:
                unverified.append(c.name)
                checks.append({"capability": c.name, "verified": None, "reason": "no_example"})
                continue
            sample = ex[0]
            try:
                a = sample.get("args", {"_value": sample.get("input", sample)}) or {}
                ref = run_reference(bundle_dir, c.entry_function, a)
                got = getattr(mod, c.entry_function)(**a)
                ok = compare(c.entry_function, ref, got)
                verified += int(ok)
                checks.append({"capability": c.name, "verified": ok, "ref": str(ref)[:120], "got": str(got)[:120]})
            except Exception as e:
                checks.append({"capability": c.name, "verified": False, "reason": f"{type(e).__name__}: {e}"})
        n_verifiable = sum(1 for c in checks if c.get("verified") is not None)
        res["steps"]["verification"] = {"verified": verified, "n_verifiable": n_verifiable,
                                        "unverified_no_example": unverified, "checks": checks}
        res["capability_verification_rate"] = (verified / n_verifiable) if n_verifiable else 0.0
        res["success"] = n_verifiable > 0 and verified == n_verifiable
        res["capability_verification_rate_all"] = (verified / len(checks)) if checks else 0.0
    else:
        res["success"] = True  # build-only success if verify disabled

    return res
