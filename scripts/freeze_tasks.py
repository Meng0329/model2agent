"""Freeze the pilot benchmark BEFORE evaluation.

Builds, for each pilot asset, 3 tutorial-derived + 3 novel predict tasks and a set of
capability-verification examples. Every reference output is produced by executing the
ORIGINAL model (reference execution) — never hard-coded, never from an evaluated agent.
Writes results/frozen/tasks.json.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model2agent.verification.reference_exec import run_reference

OUT = ROOT / "results" / "frozen"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20261029


def _novel_inputs_digits(n, exclude):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    d = load_digits(); X, y = d.data, d.target
    _, Xte, _, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    ex = {tuple(round(float(v), 6) for v in e) for e in exclude}
    out = []
    for i in range(len(Xte)):
        key = tuple(round(float(v), 6) for v in Xte[i])
        if key in ex: continue
        out.append(Xte[i].tolist())
        if len(out) == n: break
    return out


def _novel_inputs_cancer(n, exclude):
    from sklearn.datasets import load_breast_cancer
    from sklearn.model_selection import train_test_split
    d = load_breast_cancer(); X, y = d.data, d.target
    _, Xte, _, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    ex = {tuple(round(float(v), 6) for v in e) for e in exclude}
    out = []
    for i in range(len(Xte)):
        key = tuple(round(float(v), 6) for v in Xte[i])
        if key in ex: continue
        out.append(Xte[i].tolist())
        if len(out) == n: break
    return out


def build():
    tasks = []
    cap_examples = {}

    # ---- cnn_digits ----
    slug = "cnn_digits"; bdir = ROOT / "model_assets" / slug
    ex = json.loads((bdir / "examples.json").read_text())
    tut_inputs = [e["args"]["features"] for e in ex["predict"][:3]]
    novel_inputs = _novel_inputs_digits(3, [e["args"]["features"] for e in ex["predict"]])
    for i, inp in enumerate(tut_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-tutorial-{i}", "slug": slug, "split": "tutorial",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    for i, inp in enumerate(novel_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-novel-{i}", "slug": slug, "split": "novel",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    cap_examples[slug] = {}
    for cap, argfn in [("predict", lambda: {"features": tut_inputs[0]}),
                       ("predict_proba", lambda: {"features": tut_inputs[0]}),
                       ("saliency", lambda: {"features": tut_inputs[0], "top_k": 5}),
                       ("classes", lambda: {})]:
        try:
            a = argfn(); ref = run_reference(bdir, cap, a)
            cap_examples[slug][cap] = {"args": a, "reference_output": ref,
                                       "nl_prompt": f"Run capability `{cap}` with args {json.dumps(a)}."}
        except Exception as e:
            cap_examples[slug][cap] = {"error": f"{type(e).__name__}: {e}"}

    # ---- xgb_tabular ----
    slug = "xgb_tabular"; bdir = ROOT / "model_assets" / slug
    ex = json.loads((bdir / "examples.json").read_text())
    tut_inputs = [e["args"]["features"] for e in ex["predict"][:3]]
    novel_inputs = _novel_inputs_cancer(3, [e["args"]["features"] for e in ex["predict"]])
    for i, inp in enumerate(tut_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-tutorial-{i}", "slug": slug, "split": "tutorial",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    for i, inp in enumerate(novel_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-novel-{i}", "slug": slug, "split": "novel",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    cap_examples[slug] = {}
    for cap, argfn in [("predict", lambda: {"features": tut_inputs[0]}),
                       ("predict_proba", lambda: {"features": tut_inputs[0]}),
                       ("explain", lambda: {"top_k": 5}),
                       ("classes", lambda: {})]:
        try:
            a = argfn(); ref = run_reference(bdir, cap, a)
            cap_examples[slug][cap] = {"args": a, "reference_output": ref,
                                       "nl_prompt": f"Run capability `{cap}` with args {json.dumps(a)}."}
        except Exception as e:
            cap_examples[slug][cap] = {"error": f"{type(e).__name__}: {e}"}

    # ---- xgb_tabular ----
    slug = "xgb_tabular"; bdir = ROOT / "model_assets" / slug
    ex = json.loads((bdir / "examples.json").read_text())
    tut_inputs = [e["args"]["features"] for e in ex["predict"][:3]]
    novel_inputs = _novel_inputs_cancer(3, [e["args"]["features"] for e in ex["predict"]])
    for i, inp in enumerate(tut_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-tutorial-{i}", "slug": slug, "split": "tutorial",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    for i, inp in enumerate(novel_inputs):
        args = {"features": inp}
        ref = run_reference(bdir, "predict", args)
        tasks.append({"task_id": f"{slug}-novel-{i}", "slug": slug, "split": "novel",
                      "capability": "predict", "args": args, "reference_output": ref, "check": "exact",
                      "nl_prompt": f"Use the `predict` capability with args {{\"features\": {json.dumps(inp)}}}. Return the model's raw output."})
    cap_examples[slug] = {}
    for cap, argfn in [("predict", lambda: {"features": tut_inputs[0]}),
                       ("predict_proba", lambda: {"features": tut_inputs[0]}),
                       ("explain", lambda: {"top_k": 5}),
                       ("classes", lambda: {})]:
        try:
            a = argfn(); ref = run_reference(bdir, cap, a)
            cap_examples[slug][cap] = {"args": a, "reference_output": ref,
                                       "nl_prompt": f"Run capability `{cap}` with args {json.dumps(a)}."}
        except Exception as e:
            cap_examples[slug][cap] = {"error": f"{type(e).__name__}: {e}"}

    (OUT / "tasks.json").write_text(json.dumps({"frozen": True, "n_tasks": len(tasks),
                                                "tasks": tasks, "capability_examples": cap_examples},
                                               ensure_ascii=False, indent=2))
    print(f"froze {len(tasks)} tasks -> {OUT/'tasks.json'}")
    for s in cap_examples:
        ok = sum(1 for v in cap_examples[s].values() if "error" not in v)
        print(f"  {s}: {ok} capability examples with reference outputs")
    return OUT / "tasks.json"


if __name__ == "__main__":
    build()
