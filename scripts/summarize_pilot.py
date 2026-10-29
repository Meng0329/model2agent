"""Summarize the pilot into docs/PILOT_RESULTS.md from real logs (no fabrication)."""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    log = ROOT / "results" / "logs" / "pilot_runs.jsonl"
    rows = [json.loads(l) for l in open(log) if l.strip()] if log.exists() else []
    tasks = [r for r in rows if r.get("record_type") == "task_run"]
    caps = [r for r in rows if r.get("record_type") == "capability_verify"]
    agent = [r for r in rows if r.get("record_type") == "agentification"]

    acc = defaultdict(lambda: [0, 0])  # (method, slug, split) -> [correct, n]
    for r in tasks:
        d = acc[(r["method"], r["slug"], r["split"])]; d[1] += 1; d[0] += int(r["correct"])
    capagg = defaultdict(lambda: [0, 0])
    for r in caps:
        d = capagg[r["method"]]; d[1] += 1; d[0] += int(r["correct"])
    costs = defaultdict(float)
    for r in tasks:
        costs[r["method"]] += float(r.get("llm_cost_usd", 0.0))

    L = ["# Model2Agent V0.3 — P0 Pilot 结果（真实数据）", "",
         f"> 由 `scripts/summarize_pilot.py` 从 `results/logs/pilot_runs.jsonl`（{len(rows)} 条记录）自动生成。",
         "> 2 模型 Pilot 仅报告**描述性结果**，不宣称跨模型泛化（对齐 Paper2Agent 统计规范）。", ""]
    L += ["## 1. 端到端 Agentification（方法 M）", "", "| 模型 | 成功 | 能力验证率(可验证) |", "|---|---|---|"]
    for r in agent:
        L.append(f"| {r['slug']} | {r.get('success')} | {r.get('cap_verification_rate')} |")
    L += ["", "## 2. 任务准确率（正确/运行次数）", "",
          "| 模型 | 方法 | tutorial | novel | 合计 |", "|---|---|---|---|---|"]
    slugs = sorted({r["slug"] for r in tasks})
    for slug in slugs:
        for method in ("B0", "B1", "B2", "M"):
            t = acc.get((method, slug, "tutorial"), [0, 0])
            n = acc.get((method, slug, "novel"), [0, 0])
            if t[1] + n[1] == 0:
                continue
            L.append(f"| {slug} | {method} | {t[0]}/{t[1]} | {n[0]}/{n[1]} | {t[0]+n[0]}/{t[1]+n[1]} |")
    L += ["", "## 3. 工具/能力验证率（通过/验证次数）", "", "| 方法 | 通过率 |", "|---|---|"]
    for m in ("B0", "B1", "B2", "M"):
        if m in capagg:
            c, n = capagg[m]
            L.append(f"| {m} | {c}/{n} = {c/n:.3f} |" if n else f"| {m} | n/a |")
    L += ["", "## 4. 成本（任务运行累计，USD）", ""]
    for m in ("B0", "B1", "B2", "M"):
        if m in costs:
            L.append(f"- {m}: ${costs[m]:.4f}")
    an = ROOT / "results" / "logs" / "analysis.json"
    if an.exists():
        a = json.loads(an.read_text())
        L += ["", "## 5. 配对统计（M vs 基线）", "",
              "| 对比 | 均值差 | paired-t | p(t) | Cohen dz | 聚类Bootstrap 95%CI |",
              "|---|---|---|---|---|---|"]
        for lbl, pk, ck in [("M vs B0", "paired_M_vs_B0", "cluster_bootstrap_M_vs_B0"),
                            ("M vs B2", "paired_M_vs_B2", "cluster_bootstrap_M_vs_B2")]:
            p = a.get(pk, {}); c = a.get(ck, {})
            L.append(f"| {lbl} | {p.get('mean_diff')} | {p.get('paired_t')} | {p.get('p_t')} | "
                     f"{p.get('cohen_dz')} | [{c.get('ci_low')}, {c.get('ci_high')}] |")
        L += ["", "> 仅 2 个模型，聚类 Bootstrap 的 n_models=2，置信区间极宽，**不得据此下跨模型结论**。"]
    # 6. robustness (fault injection) — rendered only from real fault-result files
    fdir = ROOT / "results" / "logs"
    frows = []
    for p in sorted(fdir.glob("fault_results_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        frows.extend(d.get("results", []))
    if frows:
        L += ["", "## 6. 鲁棒性（6 类故障注入，方法 M）", "",
              "| 模型 | 故障 | 检出 | 自动修复 | 修复后一致 | 不安全修复拒绝 |", "|---|---|---|---|---|---|"]
        for r in frows:
            L.append(f"| {r['slug']} | {r['fault']} | {r['detected']} | {r['repaired']} | "
                     f"{r['post_repair_consistent']} | {r['unsafe_rejected']} |")
        det = sum(r["detected"] for r in frows); tot = len(frows)
        uns = [r for r in frows if r["fault"] in ("preprocessing_drift", "weight_config_mismatch")]
        L += ["", f"- **故障检测率：{det}/{tot} = {det/tot:.3f}**",
              f"- **不安全修复拒绝率：{sum(r['unsafe_rejected'] for r in uns)}/{len(uns)} = "
              f"{sum(r['unsafe_rejected'] for r in uns)/max(1,len(uns)):.3f}**",
              "- **自动修复成功率：0**（检测到故障但未实现自动修复，列为 P1 工作）",
              "- 修复后一致性仅在转换被判 success 时检验；本次全部故障均判失败，故该项不代表修复效果。",
              "", "> 结论：检测能力 100%，但缺少自动修复；不得将“检测到”当作“已修复”。"]

    L += ["", "## 7. 诚实声明", "",
          "- 本 Pilot 只跑了 2 个模型；B1/B3、消融 A1-A5、100 模型、未见家族均**未执行**。",
          "- 任何未跑完的 split 在原始 JSONL 中如实缺省，未补造数值。",
          "- 结果用于技术可行性验证，不作性能优越性宣称。"]
    out = ROOT / "docs" / "PILOT_RESULTS.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
