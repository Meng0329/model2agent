"""Reproducibility report generator (Paper2Agent §11 alignment).

Collects: git commit, model revisions/hashes (from metrics.json per asset), prompt/skill
versions, Claude Agent SDK + DeepSeek model IDs, Python & dependency versions, random seed,
GPU info, and a pointer to raw JSONL logs + per-call cost CSV. Writes results/logs/reproducibility.json.
Secrets and private LLM chain-of-thought are explicitly excluded.
"""
from __future__ import annotations
import json, platform, subprocess, sys, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from model2agent import config


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def _model_revisions() -> dict:
    out = {}
    for b in sorted(config.MODEL_ASSETS_DIR.iterdir()):
        if not (b / "manifest.json").exists():
            continue
        m = json.loads((b / "manifest.json").read_text())
        metrics = {}
        if (b / "metrics.json").exists():
            metrics = json.loads((b / "metrics.json").read_text())
        out[b.name] = {
            "model_id": m.get("model_id"), "revision": m.get("revision"),
            "framework": m.get("framework"), "weights_sha256": (metrics.get("weights_sha256")
                                                              or m.get("weights_path") and "see_asset"),
            "test_metric": {k: metrics[k] for k in ("test_accuracy", "n_train", "n_test")
                            if k in metrics},
        }
    return out


def _deps() -> dict:
    import importlib.metadata as md
    pkgs = ["torch", "transformers", "scikit-learn", "xgboost", "pandas", "numpy",
            "scipy", "openai", "claude-agent-sdk", "anthropic", "gradio", "pytest"]
    out = {}
    for p in pkgs:
        try:
            out[p] = md.version(p)
        except Exception:
            out[p] = "n/a"
    return out


def _gpu() -> dict:
    if torch.cuda.is_available():
        return {"visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "name": torch.cuda.get_device_name(0),
                "count": torch.cuda.device_count()}
    return {"visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "name": "cpu"}


def build():
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Secrets and private LLM chain-of-thought are intentionally excluded.",
        "git_commit": _git_commit(),
        "seed": config.RANDOM_SEED,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "deepseek_model_id": config.DEEPSEEK_MODEL,
        "deepseek_base_url": config.DEEPSEEK_BASE_URL,
        "claude_sdk_available": config.CLAUDE_SDK_AVAILABLE,
        "dependencies": _deps(),
        "gpu": _gpu(),
        "models": _model_revisions(),
        "artifacts": {
            "frozen_tasks": str(ROOT / "results" / "frozen" / "tasks.json"),
            "raw_logs": str(ROOT / "results" / "logs" / "pilot_runs.jsonl"),
            "summary": str(ROOT / "results" / "logs" / "pilot_summary.json"),
            "analysis": str(ROOT / "results" / "logs" / "analysis.json"),
            "cost_csv": str(ROOT / "results" / "csv" / "summary.csv"),
        },
    }
    out = ROOT / "results" / "logs" / "reproducibility.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=False))
