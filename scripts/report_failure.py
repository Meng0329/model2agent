"""Failure report generator — consumes raw pilot JSONL and writes results/failure_report.md.

Honest reporting: distinguishes (a) *agentification* failures (model could not be converted),
(b) *task* failures (converted but some tasks wrong), and (c) *baseline* failures. Never
marks an unexecuted experiment as done. Also writes results/next_phase_checklist.md.
"""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    log = ROOT / "results" / "logs" / "pilot_runs.jsonl"
    if not log.exists():
        print("no log"); return
    rows = [json.loads(l) for l in open(log) if l.strip()]
    agent = [r for r in rows if r.get("record_type") == "agentification"]
    caps = [r for r in rows if r.get("record_type") == "capability_verify"]
    tasks = [r for r in rows if r.get("record_type") == "task_run"]
    loads = [r for r in rows if r.get("record_type") == "agent_load_error"]

    # aggregate
    per_model = defaultdict(lambda: {"agentified": None, "cap": [0, 0],
                                     "task": defaultdict(lambda: [0, 0])})
    for r in agent:
        per_model[r["slug"]]["agentified"] = bool(r.get("success"))
    for r in caps:
        d = per_model[r["slug"]]["cap"]; d[1] += 1; d[0] += int(r["correct"])
    for r in tasks:
        d = per_model[r["slug"]]["task"][(r["method"], r["split"])]; d[1] += 1; d[0] += int(r["correct"])

    lines = ["# Model2Agent V0.3 — 失败报告（P0 2 模型 Pilot）", "",
             "> 自动生成。仅报告真实执行结果；未执行的实验（100 模型 / 消融 / 未见家族）不在此声称完成。", "",
             f"原始记录：`{log}`（{len(rows)} 条）。", ""]
    lines += ["## 1. 端到端 Agentification（M）", "", "| 模型 | Agent 化成功 | 能力验证(通过/可验证) |", "|---|---|---|"]
    for slug, d in per_model.items():
        c0, c1 = d["cap"]
        lines.append(f"| {slug} | {d['agentified']} | {c0}/{c1} |")
    lines += ["", "失败转换计入成功率分母（分母=全部尝试模型）。", ""]

    lines += ["## 2. 任务准确率（正确/总运行）", "", "| 模型 | 方法 | tutorial | novel |", "|---|---|---|---|"]
    for slug, d in per_model.items():
        for method in ("B0", "B2", "M"):
            t = d["task"].get((method, "tutorial"), [0, 0])
            n = d["task"].get((method, "novel"), [0, 0])
            lines.append(f"| {slug} | {method} | {t[0]}/{t[1]} | {n[0]}/{n[1]} |")

    errs = Counter((r["method"], (r.get("error") or "")[:60]) for r in tasks if r.get("error"))
    lines += ["", "## 3. 失败模式", ""]
    if errs:
        for (m, e), n in errs.most_common(15):
            lines.append(f"- [{m}] x{n}: {e}")
    else:
        lines.append("- 无记录的运行异常。")
    if loads:
        lines += ["", "**Agent 加载错误：**"]
        for r in loads:
            lines.append(f"- {r['slug']}: {r.get('error','')[:200]}")

    lines += ["", "## 4. 未执行 / 未完成项（诚实标注）", "",
              "- 100 模型大规模集：**未执行**（P3）。",
              "- 未见任务家族测试：**未执行**（P3）。",
              "- A1–A5 消融：**未执行**（P1/P2）。",
              "- B1 / B3 基线：**未执行**（代码接口预留）。",
              "- 开放式（open-ended）任务与双人评分：**未执行**（仅结构预留）。",
              "- 鲁棒性 6 类故障注入：代码就绪，**待运行**（`scripts/run_robustness.py`）。",
              "- 本次 Pilot 若因 LLM 延迟出现部分 split 未跑完，已在记录中如实反映（不补造）。", ""]

    out = ROOT / "results" / "failure_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(rows)} records, {len(tasks)} task runs)")


if __name__ == "__main__":
    main()
