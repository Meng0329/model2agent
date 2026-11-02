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
| rice-R2-closed-loop | ✅ SISR，7 次修订 | ❌ | ✅ | ✅ | ✅（2 次独立复跑） |
| rice-R3-rediscovery | ✅ SISR，2 次修订 | ❌ | ✅ | ✅ | ✅（2 次独立复跑） |
| protein-P1-novel | ✅ SISR，2 次修订 | ❌ | ✅ | ✅ | ✅ |
| protein-P2-closed-loop | ✅ SISR（无修订） | ❌ | ✅ | ❌ | ✅ |
| protein-P3-rediscovery | ❌ SISR（100 次调用、20 次 oracle、有修订） | ❌ | ❌ | ❌ | ❌ |

汇总（全部 30 格均运行，无 NOT_TESTED；harness 缺陷 run 已剔出，B3 在 R2/R3 各 2 次独立
复跑）：**M SISR=5/6 (0.833)**，B0=0/6，B1=5/6 (0.833)，B2=4/6 (0.667)，
B3=7/8 (0.875)。SEV：M=1.0，B1=0.833，B2=0.667，B3=0.875。均成本：M $1.87，B1 $2.05，
B2 $2.04，B3 $2.16，B0 $0.74。

**如实结论**：在 S1 这些任务上，结构化基线（B1/B3）的 SISR **不低于** M（B3 略高、B1 相同），
B2 在 protein-P2 独有失败但仍更便宜；H1（M > 基线）在本基准上**未获支持**。M 的唯一可测差异
是**显式、可审计的假设修订**：M 在 4/6 任务记录到 adaptation_success（P1、R2、R3、P3），
B1/B3 在全部任务均为 0——即 M 在有证据反馈时会改写假设，基线从不改写。protein-P3 再发现对
**全部五种方法**均失败（M 甚至做了 100 次真实模型调用与 20 次 oracle 查询、且结论 SEV=1.0），
属任务/模型难度（ESM-2 零样本 + 20 次测量不足以可靠定位该 assay 的最优单突变），非 M 特有缺陷。

S1 门禁（两域各 ≥1 完整任务；基线共享同 LLM/SDK/预算/oracle；失败如实；30/30 格已运行）
**已达成**；但 H1 在本基准上**未获支持**，按协议如实报告，不改为正向结论。

## S2（本轮部分）— 消融与内部效度

- [x] **A5 无证据反馈重规划**（部分）：rice-R2 闭环上 B1（无反馈环）与 M 均 SISR 成功，
      但 M 记录 7 次显式假设修订、B1 为 0——成功率无差，过程可审计性有差（ASIG 未定义）。
- [x] **A6 无独立验证**（结构性）：所有 M 结论均由 evaluator 用隐藏 oracle 独立判分，
      不依赖 agent 自述；未运行"无独立验证"的对照 run。
- [x] **矛盾证据响应（观察性，非受控注入）**：`scripts/run_scientist_ablations.py
      --contradiction-audit` 在真实 S1 M ledgers 上检测 E1 预测 vs E3 实测的矛盾
      （模型 top-K 候选实测值低于该 run E3 中位数）。结果：
      protein-P1 有 2 处矛盾（R23K、R35K）且 M 记录 2 次修订（responded=True）；
      protein-P3 有 2 处矛盾（H40K、H40N）且 M 记录 1 次修订（responded=True）；
      protein-P2 有 3 处矛盾但 M **未**记录修订（responded=False）；
      rice-R2/R3 的模型 top 预测被实测证实（0 矛盾）。来源：
      `results/logs/scientist_contradiction_audit.json`。**这不是受控注入**（测量值均为
      agent 真实查询所得，未伪造），只作观察性证据。
- [x] **A1 无 SAD / 能力图**（真·编译消融，rice-R2，n=1）：用去掉 `affordance-analyst`
      与 `capability-graph-builder` 的编译器重新生成 scientist 项目并真实运行评分。
      结果：编译 OBSERVED（gen $3.03），**SISR=True / oracle=True / SEV=0.75 / 1 次修订 /
      2 次模型调用 / 运行 $1.42**。SEV 下降是真实测量（C1 声明了 E1/E2/E3，但只引用到
      E1+E3 记录，按评分规则判为 unsupported），不是 harness 缺陷。
      来源：`results/logs/scientist_ablations.jsonl`。
- [x] **A9 外层单智能体 vs 多智能体**（同预算，rice-R2，n=1）：单智能体编译器
      （`agents={}`）生成并真实运行。结果：编译 OBSERVED（gen $3.31），
      **SISR=True / oracle=True / SEV=1.0 / 1 次修订 / 2 次模型调用 / 运行 $1.42**。
      对照 S1 的完整 M（rice-R2）：SISR=True / SEV=1.0 / **7 次修订** / 1 次调用 / $1.96。
- **S2 消融的如实结论（n=1，仅描述性）**：在 rice-R2 这个已饱和任务上，去掉外层多智能体
  （A9）或去掉能力图/affordance（A1）都**没有丢失 SISR 成功**——即结构不是该任务成功的
  必要条件。可测差异在证据审计质量与自适应修订：A1 的 SEV 降到 0.75，完整 M 记录到 7 次
  修订（两个消融各仅 1 次）。这与 S1 主结论一致：结构主要影响**可审计性与证据接地**，
  而非饱和任务上的原始成功率。
- [ ] 配对统计 + 域宏平均：S1 每格 n=1、S2 每格 n=1，仅描述性，不做显著性

## S3（本轮不做，标 NOT_TESTED）

- [ ] 第三/第四科学域（材料 CHGNet 需先验证 CHGNet 权重与 GPU0 可行性）
- [ ] HDSS 未见域泛化（需独立 held-out 域，禁止在保留域调参）
- [ ] 人工专家盲评（本轮不做，不伪造）

## 明确不做

- 不把"模型封装为工具"当作主贡献。
- 不做残缺资产恢复主线。
- 不改前端；科研工作台以 CLI/脚本 + 可追溯 ledger 交付。
- 不以 LLM 猜测值生成 `config.json`；生成只来自真实加载/执行。
