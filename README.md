# Model2Agent V3.0 — Model-to-Scientist

把一个**预训练科学模型**编译成**自主领域科学家 Agent**：它能提出可证伪假设、设计受控
计算实验、执行**真实模型**、在受预算约束的**真实历史测量**上观测、据证据修正假设，
并对未见科学领域泛化。

> 本仓库只有一条研究主线（SMSC）。旧 V0.3 的 AGCI/MCG/确定性模板生成/五段流水线
> 已移除，不保留双版本。协议与判据见 [`docs/scientist_protocol.md`](docs/scientist_protocol.md)。

## 两句话架构

1. **外层编译器** = 一个 Claude Agent SDK 会话 + 多智能体（`model-profiler`、
   `affordance-analyst`、`capability-graph-builder`、`scientist-synthesizer`、
   `verification-auditor`）。没有固定流水线、关键词路由、模拟或静默兜底。
2. **生成的 Scientist** = 单主研究 agent + 科学 Skills（MCP 工具 `run_model` /
   `plan_experiment` / `record_evidence` / `query_evidence_oracle` / `revise_hypothesis`），
   以独立子进程 `run_research.py` headless 运行。

确定性代码只做四件事：执行模型、回放真实测量（预算强制）、持久化证据账本、按冻结
判据评分。生成逻辑全部由 agent 完成。

## 目录

```
model2agent/
  scientist/        # schema、子代理、SDK 会话、生成式 runtime、runner、scorer、baselines
  oracle/           # 严格执行 oracle + 历史测量 oracle（预算/访问日志/hidden 隔离）
  verification/     # 参考执行（真实 ground truth）
  config.py         # LLM/GPU/预算/路径
model_assets/       # 真实科学模型资产：esm2_variant（蛋白）、rice_gs（水稻 GS）
results/frozen/     # scientist_tasks.json（6 个冻结任务，唯一 id，无泄漏）
results/logs/       # scientist_runs.jsonl（唯一可追溯事实源，入仓）
results/experiments/ # 每个 run 的证据/结论/最终选择/oracle 访问日志
```

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env                    # DEEPSEEK_API_KEY（唯一 secret 位置）

python3 scripts/build_scientist_benchmark.py          # 冻结任务 + hidden oracle
python3 scripts/run_scientist_pilot.py --stage S1 --methods B0 B1 B2 B3 M --reps 1
python3 scripts/run_scientist_analysis.py             # SISR/SEV/成本/配对差
```

## 指标

- **SISR**：预注册成功判据 **且** 真实模型调用 > 0 **且** 有效证据 **且** 所需产物齐全。
- **SEV**：结论的支持率；引用必须解析到证据账本 id，否则计为 unsupported。
- 辅助：模型调用数、oracle 查询数、成本、时延、假设修订次数。

未运行 = NOT_TESTED，阻塞 = BLOCKED，失败 = FAILED；从不静默改判，从不伪造测量。
