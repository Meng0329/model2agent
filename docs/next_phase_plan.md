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

## S1 — 两域各至少一个完整可验证科研任务（已完成，如实报告）

| 任务 | M | B0 | B1 | B2 | B3 |
|------|----|----|----|----|----|
| rice-R1-novel | ✅ SISR | ❌（无工具） | ✅ | ✅ | ✅ |
| rice-R2-closed-loop | ✅ SISR，7 次修订 | NOT_TESTED | ✅ | NOT_TESTED | ✅ |
| rice-R3-rediscovery | ✅ SISR | NOT_TESTED | ✅ | NOT_TESTED | ✅ |
| protein-P1-novel | ✅ SISR | ❌ | ✅ | ✅ | ✅ |
| protein-P2-closed-loop | ✅ SISR（无修订） | NOT_TESTED | ✅ | NOT_TESTED | NOT_TESTED |
| protein-P3-rediscovery | ❌ SISR | NOT_TESTED | ❌ | NOT_TESTED | NOT_TESTED |

汇总（n=1/格，非 harness 记录）：**M SISR=5/6 (0.833)**，B0=0/2，B1=5/6 (0.833)，
B2=2/2，B3=4/4。SEV：M=1.0，B1=0.833，B2/B3=1.0。均成本：M $1.87，B2 $1.42。

**如实结论**：在 S1 这些任务上，结构化基线（B1/B2/B3）不劣于 M，B2 更便宜且同成功；
M 的差异在于**显式、可审计的假设修订**（rice-R2 7 次、R3 2 次、protein-P1 2 次）与
单会话多智能体编译，而非更高成功率。protein-P3 再发现对 M 与 B1 均失败，属任务/模型
难度（ESM-2 零样本 + 20 次测量不足以可靠定位该 assay 的最优单突变），非 M 特有缺陷。

S1 门禁（两域各 ≥1 完整任务；基线共享同 LLM/SDK/预算/oracle；失败如实）**已达成**；
但 H1（M > 基线）在本基准上**未获支持**，按协议如实报告，不改为正向结论。

## S2（本轮部分）— 消融与内部效度

- [x] **A5 无证据反馈重规划**（部分）：rice-R2 闭环上 B1（无反馈环）与 M 均 SISR 成功，
      但 M 记录 7 次显式假设修订、B1 为 0——成功率无差，过程可审计性有差（ASIG 未定义）。
- [x] **A6 无独立验证**（结构性）：所有 M 结论均由 evaluator 用隐藏 oracle 独立判分，
      不依赖 agent 自述；未运行"无独立验证"的对照 run。
- [ ] A1 无 SAD / 能力图：NOT_TESTED
- [ ] A9 外层单智能体 vs 多智能体（同预算）：NOT_TESTED
- [ ] 矛盾证据注入：NOT_TESTED
- [ ] 配对统计 + 域宏平均：n=1，仅描述性，不做显著性

## S3（本轮不做，标 NOT_TESTED）

- [ ] 第三/第四科学域（材料 CHGNet 需先验证 CHGNet 权重与 GPU0 可行性）
- [ ] HDSS 未见域泛化（需独立 held-out 域，禁止在保留域调参）
- [ ] 人工专家盲评（本轮不做，不伪造）

## 明确不做

- 不把"模型封装为工具"当作主贡献。
- 不做残缺资产恢复主线。
- 不改前端；科研工作台以 CLI/脚本 + 可追溯 ledger 交付。
- 不以 LLM 猜测值生成 `config.json`；生成只来自真实加载/执行。
