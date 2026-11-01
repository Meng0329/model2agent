"""Generate an honest S1/S2 report from the append-only run ledger.

Every number is read from results/logs/scientist_runs.jsonl. Tasks or methods
that were never run are printed as NOT_TESTED — this script never fills a gap.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "results" / "logs" / "scientist_runs.jsonl"
TASKS = ROOT / "results" / "frozen" / "scientist_tasks.json"
OUT = ROOT / "results" / "scientist_s1_report.md"

METHODS = ["B0", "B1", "B2", "B3", "M"]


def _fmt(v, nd=3):
    return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def main() -> None:
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    rows = []
    if LOG.exists():
        rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Pre-fix harness failures are real runs but not evidence about the method:
    # separate them so they neither inflate nor deflate a method's success rate.
    harness = [r for r in rows if str(r.get("failure_category") or "").startswith("harness_")]
    rows_for_method = [r for r in rows if not str(r.get("failure_category") or "").startswith("harness_")]

    by = {}
    for r in rows_for_method:
        by.setdefault((r["scientific_task_id"], r["method_id"]), []).append(r)

    lines = [
        "# Model2ScientistBench — S1 报告（自动生成，来自真实 run ledger）",
        "",
        "> 数据源：`results/logs/scientist_runs.jsonl`（追加式，不可改写历史）。",
        "> 未运行的方法/任务一律标注 **NOT_TESTED**，失败标注 **FAILED**，不补造数字。",
        "> 本轮 `reps=1`；仅作描述性报告，不做显著性宣称。",
        "",
        "## 1. 逐任务结果",
        "",
        "| 任务 | 域 | 方法 | n | SISR | oracle | SEV | 模型调用 | oracle 查询 | 修订 | 成本($) | 时延(s) | 状态 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in tasks:
        for m in METHODS:
            rs = by.get((t["task_id"], m))
            if not rs:
                lines.append(f"| {t['task_id']} | {t['domain']} | {m} | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED "
                             f"| — | — | — | — | — | NOT_TESTED |")
                continue
            for r in rs:
                status = "OBSERVED" if r.get("scientific_task_success") else "FAILED"
                lines.append(
                    f"| {t['task_id']} | {t['domain']} | {m} | {len(rs)} | {r.get('scientific_task_success')} "
                    f"| {r.get('final_conclusion_validity')} | {_fmt(float(r.get('evidence_validity') or 0))} "
                    f"| {r.get('model_call_count')} | {r.get('experiment_count')} "
                    f"| {r.get('adaptation_success')} | {_fmt(float(r.get('cost') or 0))} "
                    f"| {_fmt(float(r.get('latency') or 0), 0)} | {status} |")

    lines += ["", "## 2. 按方法汇总", "",
              "| 方法 | n | SISR 率 | oracle 率 | 平均 SEV | 平均成本($) |", "|---|---|---|---|---|---|"]
    for m in METHODS:
        rs = [r for r in rows_for_method if r["method_id"] == m]
        if not rs:
            lines.append(f"| {m} | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |")
            continue
        n = len(rs)
        lines.append(
            f"| {m} | {n} | {sum(bool(r['scientific_task_success']) for r in rs)/n:.3f} "
            f"| {sum(bool(r['final_conclusion_validity']) for r in rs)/n:.3f} "
            f"| {sum(float(r['evidence_validity'] or 0) for r in rs)/n:.3f} "
            f"| {sum(float(r['cost'] or 0) for r in rs)/n:.3f} |")

    lines += ["", "## 3. 失败与未解释项（诚实标注）", ""]
    failed = [r for r in rows_for_method if not r.get("scientific_task_success")]
    if not failed:
        lines.append("- 无")
    for r in failed:
        lines.append(
            f"- **{r['method_id']} / {r['scientific_task_id']}**：FAILED。"
            f"模型调用={r.get('model_call_count')}，oracle 查询={r.get('experiment_count')}，"
            f"oracle 命中={r.get('final_conclusion_validity')}，产物合格={r.get('experiment_validity')}。")

    lines += ["", "### 3.1 修复前 harness 失败（不计入方法成功率）", ""]
    if not harness:
        lines.append("- 无")
    for r in harness:
        lines.append(
            f"- **{r['method_id']} / {r['scientific_task_id']}**："
            f"`{r.get('failure_category')}` — {r.get('notes', '')}。"
            "该 run 的真实产物已保留在 `rep0_prebug/`，修复后另行重跑。")

    tested = {(r["scientific_task_id"], r["method_id"]) for r in rows_for_method}
    missing = [(t["task_id"], m) for t in tasks for m in METHODS if (t["task_id"], m) not in tested]
    lines += ["", "## 4. NOT_TESTED（本轮未运行）", ""]
    if missing:
        for tid, m in missing:
            lines.append(f"- {tid} / {m}")
    else:
        lines.append("- 无（全部任务×全部方法均已运行）")

    lines += ["", "## 5. 局限", "",
              "- 每个（任务, 方法）n=1，不能做显著性推断；报告效应量而非 p 值。",
              "- 隐藏测量按预算强制访问；E1 预测从不当作 E3/E4。",
              "- 生成失败/未写交付物按 FAILED 计入分母，未静默剔除。", ""]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} runs, {len(missing)} NOT_TESTED cells)")


if __name__ == "__main__":
    main()
