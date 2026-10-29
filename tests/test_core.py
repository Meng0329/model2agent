"""Core pytest suite for Model2Agent V0.3 (no LLM calls where avoidable)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.agci.asset_scanner import scan_bundle
from model2agent.mcg.graph import build_mcg
from model2agent.verification.reference_exec import run_reference, compare
from model2agent.benchmark.tasks import Task, save_tasks, load_tasks


def test_scan_cnn_discovers_functions():
    d = scan_bundle(ROOT / "model_assets" / "cnn_digits")
    names = {f["name"] for f in d.functions}
    assert {"predict", "predict_proba", "saliency", "classes"} <= names
    assert d.evidence["import_error"] is None
    assert d.evidence["weights_sha256"]


def test_scan_xgb_weights_sha():
    d = scan_bundle(ROOT / "model_assets" / "xgb_tabular")
    assert d.evidence["weights_sha256"]
    assert d.task_family == "tabular_classification"


def test_mcg_edges_from_dependencies():
    caps = [
        {"name": "embed", "entry_function": "embed", "depends_on": []},
        {"name": "similarity", "entry_function": "similarity", "depends_on": ["embed"]},
    ]
    g = build_mcg("toy", caps)
    assert len(g.nodes) == 2
    assert any(e["src"] == "similarity" and e["dst"] == "embed" for e in g.edges)
    # `embed` is depended upon -> not a root; `similarity` is user-facing -> root
    assert "similarity" in g.root_capabilities
    assert "embed" not in g.root_capabilities


def test_reference_exec_matches_itself():
    bdir = ROOT / "model_assets" / "cnn_digits"
    import json as _j
    ex = _j.loads((bdir / "examples.json").read_text())
    args = ex["predict"][0]["args"]
    a = run_reference(bdir, "predict", args)
    b = run_reference(bdir, "predict", args)
    assert compare("predict", a, b)


def test_task_roundtrip(tmp_path):
    t = Task(task_id="t1", slug="s", split="tutorial", capability="predict",
             args={"features": [1, 2]}, reference_output=3, check="exact", nl_prompt="x")
    p = tmp_path / "tasks.json"
    save_tasks([t], p)
    loaded = load_tasks(p)
    assert loaded[0].task_id == "t1" and loaded[0].reference_output == 3


def test_proba_compare():
    assert compare("predict_proba", {"0": 0.5, "1": 0.5}, {"0": 0.5, "1": 0.5})
    assert not compare("predict_proba", {"0": 0.5}, {"0": 0.4, "1": 0.6})


def test_no_secrets_in_logs_or_tracked_files():
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout
    for f in out.splitlines():
        p = ROOT / f
        if p.is_file() and p.suffix in (".py", ".md", ".json", ".txt", ".toml", ".example"):
            txt = p.read_text(errors="ignore")
            assert "sk-ac8da1a908d5f984a9e2f592f23b8fa8ac" not in txt, f"secret in {f}"
            assert "lgw-fe4c5edc0f436c40fbf305029e8caa5" not in txt, f"secret in {f}"
