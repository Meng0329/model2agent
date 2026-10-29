"""Generate paper figures from REAL pilot data. Missing-data figures emit a template
(never fabricated numbers), and a manifest records which are data-driven.

Run: python scripts/make_figures.py
Outputs: results/figures/fig{1..5}_*.png + results/figures/manifest.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
MANIFEST = {}


def _fig(name, data_driven, note=""):
    MANIFEST[name] = {"data_driven": data_driven, "note": note}


def fig1_framework():
    """Figure 1 — Model2Agent framework (schematic of the implemented pipeline)."""
    stages = ["Model Asset\n(weights+infer+\ncard+examples)", "AGCI\nasset scan",
              "Capability\nInduction", "MCG\n(graph)", "Uniform Agent\nBuild",
              "Reference-Exec\nVerification", "Standalone\nModel Agent"]
    fig, ax = plt.subplots(figsize=(13, 2.8))
    ax.axis("off")
    for i, s in enumerate(stages):
        ax.add_patch(plt.Rectangle((i * 1.8, 0.2), 1.5, 0.9, fill=True, fc="#e8f0fe", ec="#1a73e8"))
        ax.text(i * 1.8 + 0.75, 0.65, s, ha="center", va="center", fontsize=8)
        if i < len(stages) - 1:
            ax.annotate("", xy=(i * 1.8 + 1.8, 0.65), xytext=(i * 1.8 + 1.5, 0.65),
                        arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.set_xlim(-0.1, len(stages) * 1.8); ax.set_ylim(0, 1.3)
    ax.set_title("Figure 1. Model2Agent framework (AGCI -> MCG -> Agent -> Verification)", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "fig1_framework.png", dpi=150); plt.close(fig)
    _fig("fig1_framework.png", False, "Schematic of the implemented pipeline (not a data plot).")


def fig2_case_studies(summary):
    """Figure 2 — per-model accuracy + latency for M vs baselines."""
    if not summary:
        return _template("fig2_case_studies.png", "Figure 2. Model Agent case studies (no data)")
    methods = [m for m in ("B0", "B2", "M") if m in summary]
    acc = [summary[m]["task_correct"] / max(1, summary[m]["task_total"]) for m in methods]
    lat = [summary[m]["latency_ms"] / max(1, summary[m]["task_total"] + summary[m]["cap_total"]) for m in methods]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    axes[0].bar(methods, acc, color=["#999", "#4a90d9", "#1a9850"])
    axes[0].set_ylabel("Task accuracy"); axes[0].set_ylim(0, 1.05); axes[0].set_title("Task accuracy (all models)")
    axes[1].bar(methods, lat, color=["#999", "#4a90d9", "#1a9850"])
    axes[1].set_ylabel("avg latency (ms)"); axes[1].set_title("Query latency")
    fig.suptitle("Figure 2. Pilot case studies: B0 vs B2 vs M (2 models)", fontsize=11)
    fig.tight_layout(); fig.savefig(FIG / "fig2_case_studies.png", dpi=150); plt.close(fig)
    _fig("fig2_case_studies.png", True, "From results/logs/pilot_summary.json.")


def fig3_scale():
    """Figure 3 — large-scale agentification (needs 100 models; template only for pilot)."""
    _template("fig3_large_scale.png", "Figure 3. Large-scale agentification (N=100 models)\n[PILOT: only 2 models available — template]")


def fig4_ablation():
    """Figure 4 — generalization & ablation (needs P2 ablation runs; template for pilot)."""
    _template("fig4_ablation.png", "Figure 4. Generalization & ablation (A1-A5)\n[PILOT: ablations not yet run — template]")


def fig5_robustness():
    """Figure 5 — robustness. Data-driven if fault results exist."""
    fdir = ROOT / "results" / "logs"
    files = sorted(fdir.glob("fault_results_*.json"))
    if not files:
        return _template("fig5_robustness.png", "Figure 5. Robustness & collaboration\n[PILOT: fault injection not yet run — template]")
    det, rep, cons, uns = [], [], [], []
    for fp in files:
        d = json.loads(fp.read_text())
        det.append(d.get("detection_rate", 0)); rep.append(d.get("repair_rate", 0))
        cons.append(d.get("consistency_rate", 0)); uns.append(d.get("unsafe_reject_rate", 0))
    fig, ax = plt.subplots(figsize=(6, 3.4))
    x = np.arange(4); ax.bar(x, [np.mean(det), np.mean(rep), np.mean(cons), np.mean(uns)],
                             color=["#d73027", "#fc8d59", "#91cf60", "#1a9850"])
    ax.set_xticks(x); ax.set_xticklabels(["detection", "repair", "consistency", "unsafe-reject"], fontsize=8)
    ax.set_ylim(0, 1.05); ax.set_title("Figure 5. Robustness metrics (mean over injected faults)")
    fig.tight_layout(); fig.savefig(FIG / "fig5_robustness.png", dpi=150); plt.close(fig)
    _fig("fig5_robustness.png", True, f"From {len(files)} fault-result files.")


def _template(name, title):
    fig, ax = plt.subplots(figsize=(7, 3.2)); ax.axis("off")
    ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=10, color="#666")
    fig.tight_layout(); fig.savefig(FIG / name, dpi=150); plt.close(fig)
    _fig(name, False, "Template only — insufficient data (no fabricated numbers).")


def main():
    sp = ROOT / "results" / "logs" / "pilot_summary.json"
    summary = json.loads(sp.read_text()) if sp.exists() else None
    fig1_framework(); fig2_case_studies(summary); fig3_scale(); fig4_ablation(); fig5_robustness()
    (FIG / "manifest.json").write_text(json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    print("figures written to", FIG)
    for k, v in MANIFEST.items():
        print(f"  {k}: data_driven={v['data_driven']} — {v['note']}")


if __name__ == "__main__":
    main()
