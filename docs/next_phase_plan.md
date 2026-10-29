# Model2Agent 下一阶段扩展清单（P1–P4）

> 基于当前 P0（2 模型技术可行性）交付物，按用户指定的单 GPU 分阶段路线推进。
> **当前状态诚实标注**：P0 已执行（见 `results/`）；P1–P4 **尚未执行**，以下为计划，不视为已完成。

## 当前已完成（P0）

| 项 | 状态 | 证据 |
|----|------|------|
| 2 个异质模型端到端转换 | ✅ 已执行 | `cnn_digits`（PyTorch CNN, GPU0, test_acc≈0.964）、`xgb_tabular`（XGBoost, test_acc=1.0） |
| AGCI / MCG 真实实现 | ✅ | `model2agent/agci/`、`mcg/graph.py`；扫描 4 类框架资产 |
| 统一 Agent 生成（非手写） | ✅ | `builder/agent_builder.py` 模板生成 `generated_agents/<slug>/` |
| 参考推理验证 | ✅ | 两模型均在 M 下 success=True、capability verification 4/4 |
| B0 / B2 / M 三方法 | ✅ 已执行 | `results/logs/pilot_runs.jsonl` |
| 冻结 benchmark + ground truth | ✅ | `results/frozen/tasks.json`（由参考推理生成） |
| 统计脚本 | ✅ | `scripts/run_analysis.py`（配对检验 + 聚类 Bootstrap） |
| 鲁棒性框架 | ✅ 代码就绪（待运行） | `robustness/fault_injection.py`（6 类故障） |
| Figure 1–5 脚本 | ✅ | `scripts/make_figures.py`（缺数据处仅模板） |

## P1 — 方法探索（10 模型）

- [ ] 扩充到 10 个模型，覆盖开发集 4 个家族各若干：**表格分类、图像分类、文本分类、文本嵌入**（已具备 `bert_zh` 文本嵌入/分类雏形、`sklearn_digits`/`cnn_digits`/`xgb_tabular`）。
- [ ] 增加 B1（Generic Model Wrapper + Agent SDK）与 B3（在具备论文/代码的模型子集运行 Paper2Agent/Code2Skill）。
- [ ] 运行 A1–A5 消融（尤其 **A5 No Model-specific Semantics**，最关键内部效度检验）。
- [ ] 建立失败类型分类法（缺权重 / 缺依赖 / 非标准 I/O / 无语义 / 不可安全修复）。
- [ ] 校准开放式 Rubric 与双评估者流程（评分者一致性）。

## P2 — 方法冻结（30 模型）

- [ ] 验证集 30 模型：**表格回归、目标检测、异常检测**。
- [ ] 冻结 AGCI/MCG 生成算法、prompt 版本、skill 版本、Rubric。
- [ ] 完成消融与鲁棒性数字；确认 A5 是否显著。
- [ ] 成本预算估算（单次生成 / 单查询），确定重复次数可行性。

## P3 — 正式评估（100 模型，10 家族 × 10）

- [ ] 开发 40 / 验证 30 / 未见家族 30 的划分正式冻结。
- [ ] 未见家族：**语义分割、音频分类、时间序列预测**（严格保留，测试期不得加入专用 Skill/修复规则）。
- [ ] 300 tutorial + 300 novel + 3×30 open-ended，每任务 5 次独立运行。
- [ ] 全量 B0/B1/B2/B3/M 对比；失败转换计入端到端成功率分母。
- [ ] 模型级聚类 Bootstrap 95% CI；报告效应量、成本、延迟（不依赖单一 P 值）。

## P4 — 深入案例（3 模型）

- [ ] CNN、XGBoost、Transformer 代表性案例（Figure 2）。
- [ ] 开放式多步任务（≥2 实际步骤：数据校验→推理→聚合→报告）。
- [ ] 跨 Model Agent 协作（Figure 5 可选深入）。
- [ ] 详细解释与不确定性分析。

## 关键风险与对策

1. **底层 LLM 预训练覆盖**：DeepSeek 可能见过目标模型 → “未见家族”仅指对研发/调参保留，需在论文明确声明。
2. **开源模型许可/权重可得性**：按统一规则运行前筛选，无效许可或超硬件上限者剔除；转换失败不得事后移除。
3. **A5 若不显著**：需诚实报告，AGCI 的模型语义归纳可能缺乏独立贡献——这是内部效度核心问题。
4. **单 GPU 成本**：100 模型 × 6 任务 × 5 reps/方法 ≈ 3,000 次/方法，五方法上限 ~15,000 次；先估算再全量，不为省成本事后只保留好结果。
5. **Claude Agent SDK 运行时**：当前仅配置 DeepSeek 凭证，`runtime.py` 已支持 SDK 优先、DeepSeek 回退；P1 需验证 SDK 路径实际可用或明确记录为不可用基线条件。
