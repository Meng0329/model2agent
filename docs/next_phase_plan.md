# Model2Agent V3.0 — Model-to-Scientist 阶段计划（S0–S3）

> 唯一主线：预训练科学模型 → 自主领域科学家 Agent（假设 → 规划 → 真实计算实验 →
> 观测 → 证据修正 → 结论 → 迁移未见领域）。
> 旧的 Model→Tool 五段流水线不再是主线，代码在原地增删改，不保留双版本。
> 协议与判据见 `docs/scientist_protocol.md`；所有数字以
> `results/logs/scientist_runs.jsonl` 为准。未运行 = NOT_TESTED，阻塞 = BLOCKED，
> 失败 = FAILED，绝不静默改判。

## 已完成（S0）

| 项 | 状态 | 证据 |
|----|------|------|
| 证据/假设/任务/运行 schema（严格校验） | ✅ 已执行 | `model2agent/scientist/schemas.py`，`tests/test_scientist.py` |
| 严格执行 oracle（递归数值比较，无"非空即过"） | ✅ | `model2agent/oracle/execution_oracle.py` |
| 历史测量 oracle（预算强制 + 访问日志 + 0700 hidden） | ✅ | `model2agent/oracle/historical_oracle.py` |
| 追加式 Run/Evidence Ledger | ✅ | `model2agent/scientist/evidence.py` |
| 单会话多智能体外层编译器（5 个真实子代理） | ✅ | `model2agent/scientist/subagents.py`、`orchestrator.run_smsc` |
| 生成式 Scientist（单主 agent + Skills） | ✅ | `model2agent/scientist/runtime/*` |
| 独立子进程 runner + oracle 判分 | ✅ | `model2agent/scientist/runner.py` |
| 两个真实科学域资产（蛋白 ESM-2 / 水稻 GS） | ✅ | `model_assets/esm2_variant/`、`model_assets/rice_gs/` |
| 冻结 benchmark（6 任务，唯一 id，无泄漏） | ✅ | `results/frozen/scientist_tasks.json` |
| 公平基线 B0–B3 | ✅ 代码就绪 | `model2agent/scientist/methods.py` |

## S1 — 两域各至少一个完整可验证科研任务（进行中）

| 任务 | 状态 | 证据 |
|------|------|------|
| rice-R1-novel (M) | ✅ OBSERVED — SISR=true, oracle hits 10/10, SEV=1.0 (3/3), $1.32, 410s | `results/experiments/S1/rice-R1-novel/M/rep0/` |
| rice-R1-novel (B0–B3) | ⏳ 运行中 | 运行 ledger |
| protein-P1-novel (M) | ⏳ 生成+运行中 | 运行 ledger |
| rice-R2 / rice-R3 | ⬜ NOT_TESTED | — |
| protein-P2 / protein-P3 | ⬜ NOT_TESTED | — |

S1 门禁：两域各 ≥1 完整可验证任务；≥1 任务证明下一步决策受真实反馈影响；基线共享
同 LLM/SDK/任务/预算/oracle；失败如实记录。**未达成前不进入 S2 分析。**

## S2（本轮部分）— 消融与内部效度

- [ ] A5 无证据反馈重规划（one-shot vs 闭环，ASIG）
- [ ] A6 无独立验证（去掉 verification-auditor / oracle 判分）
- [ ] A1 无 SAD / 能力图
- [ ] A9 外层单智能体 vs 多智能体（同预算）
- [ ] 矛盾证据注入：真实反向证据下的识别与修订（不伪造测量）
- [ ] 配对统计 + 域宏平均；跨 0 的不确定性如实报告

## S3（本轮不做，标 NOT_TESTED）

- [ ] 第三/第四科学域（材料 CHGNet 需先验证 CHGNet 权重与 GPU0 可行性）
- [ ] HDSS 未见域泛化（需独立 held-out 域，禁止在保留域调参）
- [ ] 人工专家盲评（本轮不做，不伪造）

## 明确不做

- 不把"模型封装为工具"当作主贡献。
- 不做残缺资产恢复主线。
- 不改前端；科研工作台以 CLI/脚本 + 可追溯 ledger 交付。
- 不以 LLM 猜测值生成 `config.json`；生成只来自真实加载/执行。
