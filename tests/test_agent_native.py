"""Agent-native pipeline tests: real generation, real prediction, project-local store.

These are developer regression tests. The PRODUCT verification is the outer
Model2Agent agent's `verify_agent` tool (backend/gen_cli.build_verify_report).
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.generator import generate  # noqa: E402


def _project(task_id: str, asset: str) -> Path:
    return generate(task_id, ROOT / "model_assets" / asset)


def test_cnn_generation_is_grounded_and_polarity_is_correct():
    proj = _project("pytest_cnn", "cnn_digits")
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    ui = json.loads((proj / "agent_ui.json").read_text(encoding="utf-8"))

    assert cfg["input_type"] == "image"
    assert cfg["labels"] == [str(i) for i in range(10)]
    assert cfg["image_preprocess"]["ink_polarity"] == "ink_on_dark"
    assert len(ui["presets"]) == 3
    assert ui["input"]["mode"] == "image"

    # Real full chain inside the generated project: fixture PNG -> adapter -> predict.
    code = r"""
import io, json
from pathlib import Path
import numpy as np
from PIL import Image
import adapters, model_exec
fx = Path("assets/cnn_digits/test/fixture_9.png").read_bytes()
feats, trace = adapters.image_to_features_with_trace(fx)
img = Image.open(io.BytesIO(fx)).convert("L").resize((8, 8))
naive = [float(x) for x in (np.asarray(img, float) / 255 * 16).flatten()]
print(json.dumps({"predict": model_exec.run("predict", {"features": feats}),
                  "naive": model_exec.run("predict", {"features": naive}),
                  "polarity": trace["ink_polarity"]}))
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=str(proj),
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["predict"] == 9
    assert out["naive"] != 9, "the old non-inverting adapter must fail this fixture"
    assert out["polarity"] == "ink_on_dark"

    # Regression: a real user upload (clean but slightly slanted/thick "0").
    # Aspect-preserving resize used to squash it into a 4-like 8x8 grid; the
    # dataset-faithful size normalization (bbox -> full canvas) must yield 0.
    code = r"""
import json
from pathlib import Path
import adapters, model_exec
fx = Path("assets/cnn_digits/test/fixture_0_slanted.png").read_bytes()
feats, trace = adapters.image_to_features_with_trace(fx)
print(json.dumps({"predict": model_exec.run("predict", {"features": feats}),
                  "grid": trace["grid"], "ink": trace["ink_polarity"]}))
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=str(proj),
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ink"] == "ink_on_dark"
    assert len(out["grid"]) == 8 and len(out["grid"][0]) == 8
    assert out["predict"] == 0, "slanted real 0 must not collapse into a 4-like grid"


def test_xgb_generation_adapts_to_tabular_without_model_specific_rules():
    proj = _project("pytest_xgb", "xgb_tabular")
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    ui = json.loads((proj / "agent_ui.json").read_text(encoding="utf-8"))

    assert cfg["input_type"] == "tabular"
    assert len(cfg["feature_names"]) == 30
    assert cfg["labels"] == ["malignant", "benign"]
    assert "image_preprocess" not in cfg
    assert ui["input"]["mode"] == "tabular"
    assert len(ui["presets"]) == 3
    assert "explain" in ui["result_views"]


def test_generator_has_no_guessing_fallback():
    src = (ROOT / "backend" / "generator.py").read_text(encoding="utf-8")
    assert "_detect_input_type" not in src
    assert "true_label" not in src
    assert "return \"text\"" not in src


def _load_store(tmp_path: Path):
    spec = importlib.util.spec_from_file_location(
        "m2a_generated_store", ROOT / "generated_agent_template" / "store.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._STORE = tmp_path / "conversations.json"
    return mod


def test_conversations_store_crud(tmp_path):
    store = _load_store(tmp_path)
    c = store.create_conversation()
    assert store.list_conversations()[0]["id"] == c["id"]
    store.append_message(c["id"], "user", "hello")
    store.append_message(c["id"], "assistant", "world")
    msgs = store.get_messages(c["id"])
    assert [m["content"] for m in msgs] == ["hello", "world"]
    assert store.clear_conversation(c["id"]) is True
    assert store.get_messages(c["id"]) == []
    assert store.delete_conversation(c["id"]) is True
    assert store.list_conversations() == []
