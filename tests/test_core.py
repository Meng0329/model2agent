"""Core pytest suite for Model2Agent V3.0 (Model-to-Scientist).

Old V0.3 AGCI/MCG/benchmark-task tests were removed with the pipeline they
covered. This suite keeps the cross-cutting invariants: reference execution,
strict numeric comparison, grounded introspection, and the no-secrets rule.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.verification.reference_exec import run_reference, compare  # noqa: E402
from model2agent.scientist.model_introspection import inspect_model  # noqa: E402
from model2agent.oracle.execution_oracle import compare_values  # noqa: E402


def test_reference_exec_matches_itself():
    bdir = ROOT / "model_assets" / "cnn_digits"
    ex = json.loads((bdir / "examples.json").read_text())
    args = ex["predict"][0]["args"]
    a = run_reference(bdir, "predict", args)
    b = run_reference(bdir, "predict", args)
    assert compare("predict", a, b)


def test_proba_compare():
    assert compare("predict_proba", {"0": 0.5, "1": 0.5}, {"0": 0.5, "1": 0.5})
    assert not compare("predict_proba", {"0": 0.5}, {"0": 0.4, "1": 0.6})


def test_execution_oracle_no_none_pass():
    # a None result is never a success; comparison must be strict and recursive
    assert not compare_values({"a": 1.0}, {"a": None}, 0.03, 1e-6)
    assert compare_values({"a": [1.0, 2.0]}, {"a": [1.0, 2.0]}, 0.03, 1e-6)
    assert not compare_values({"a": [1.0, 2.0]}, {"a": [1.0, 2.1]}, 0.03, 1e-6)


def test_inspect_cnn_discovers_functions():
    facts = inspect_model(ROOT / "model_assets" / "cnn_digits")
    assert facts.weights_sha256
    assert facts.import_error is None
    assert "predict" in facts.callable_functions
    assert facts.executed_examples, "introspection must run real examples"


def test_inspect_rice_grounded():
    facts = inspect_model(ROOT / "model_assets" / "rice_gs")
    assert facts.weights_sha256
    assert "rank_candidates" in facts.callable_functions


def test_no_secrets_in_logs_or_tracked_files():
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout
    for f in out.splitlines():
        p = ROOT / f
        if p.is_file() and p.suffix in (".py", ".md", ".json", ".txt", ".toml", ".example"):
            txt = p.read_text(errors="ignore")
            # assemble markers from fragments so this test file itself never contains a key
            sk_marker = "sk" + "-ac8da1a"
            lgw_marker = "lgw" + "-fe4c5ed"
            assert sk_marker not in txt, f"secret in {f}"
            assert lgw_marker not in txt, f"secret in {f}"
