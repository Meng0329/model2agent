# Model2Agent ↔ Paper2Agent 实验对齐记录

> 本文档为 `Model2Agent V0.3` 与 *Miao et al., "Reimagining research papers as interactive and reliable AI agents", Nature 658:1272–1280 (2026), DOI 10.1038/s41586-026-11044-y* 的实验对齐说明。
> 来源：主论文 PDF（`docs/s41586-026-11044-y.pdf`，18 页，含 Extended Data Fig.1–2）、公开仓库 `github.com/jmiao24/Paper2Agent`、预印本 arXiv:2509.06917。
> 生成日期：2026-10-29。

---

## 0. 核心定位差异（决定哪些设计不可照搬）

| 维度 | Paper2Agent | Model2Agent |
|------|-------------|-------------|
| **一级输入** | 研究论文 + 代码仓库 | 已训练模型资产（权重 + 推理代码 + 模型卡 + 示例 I/O） |
| **被转化对象** | 整篇论文（含图表、补充材料、数据集链接） | 单模型（预测 / 解释 / 不确定性 / 轻量适配） |
| **验证锚点** | 论文 tutorial 执行作为 gold standard | 原始模型参考推理（reference execution）作为 ground truth |
| **协议层** | MCP server（tools/resources/prompts） | 单体应用 + Skills 路由（**不引入 MCP 作为方法创新**） |

**关键事实（来自仓库核查）**：Paper2Agent 的 *当前* 实现已同时使用 **Skills 与 MCP**（README 描述通过 Skill 调度专业 agent、配置环境、完成验证）。因此 **“从 MCP 改为 Skills” 不能作为 Model2Agent 的核心创新**，本文档明确排除该主张。模型语义归纳（AGCI/MCG）才是本研究的方法贡献。

**图数差异**：Paper2Agent 正文只有 **Figure 1–4**（无 Figure 5）。Extended Data Fig.1（TISSUE）、Fig.2（AlphaGenome）、Fig.3（Scanpy）、Fig.4（牛皮癣因果基因协作）。本项目的 Figure 5 拟作为“跨模型协作 / 鲁棒性”**可选深入案例**，若数据不足则仅输出模板。

---

## 1. Paper2Agent 原始实验设计（已发表）

### Methods 六阶段流水线
1. **定位与克隆代码库**（从手稿/参考文献/补充材料自动识别；歧义时回退到用户 URL）
2. **环境配置**（隔离 venv + 测试配置）
3. **tutorial 发现**（输出 JSON 分类文件索引）
4. **tutorial 执行与审计**（端到端运行，捕获输入/输出/图/运行约束 → 作为 gold standard 参考）
5. **工具抽取、测试与精修**（两 agent 顺序：抽取-实现 → 测试-验证-改进；每个函数最大 **6 次修复尝试**；反复失败的函数移除 MCP 装饰器并排除）
6. **MCP server 组装**（manifest + 版本化 + 安全默认）

**验证判据**：期望文件生成；数值结果与 tutorial 输出**严格匹配（浮点 3% 容差）**；生成图经**感知哈希 Hamming<20** 匹配。失败工具**排除**而非静默保留。每个工具嵌入可追溯源码链接，工具**锁定**防幻觉。

**五个命名子 agent**：environment manager、tutorial scanner、tutorial executor、tutorial tool extractor–implementor、test verifier–improver。编排基于 Claude Agent SDK，子 agent 依次跨步骤、步骤内并行。

### Benchmark
- **AlphaGenome 案例**（Fig.2）：15 tutorial + 15 novel = 30 题，每题 **5 次独立运行** → 每方法每基准 **n=75** 次运行；**30 道开放式**研究问题由 2 名独立专家按预定义 Rubric 评分，**评分者一致性 96.7%**（基线在评估时不接触手稿/仓库）。
- **100 篇计算生物学论文**（从 bioRxiv 生物信息学类目向后回溯，不筛选文档质量/维护状态）：**74 篇成功 agent 化**；**599 个工具中提出，593 个通过自动验证**（99.0%）。
- **26 篇数据/发现型论文**（13 bioRxiv + 13 Nature，2025）：**100 道综合查询**（含重解读任务）。
- **10 个非生物学计算项目**（grf、SAELens、Binoculars、SAM2、TabPFN、GenericML、CausalImpact、Nashpy、emcee、conformal-selection）：**42 项执行型任务，5 次独立运行**。

### Baselines（原文）
| Baseline | 控制的是什么 |
|----------|--------------|
| **Claude + Repo**（本地仓库，无 MCP tools/resources/prompts，禁止抄答案） | 结构化资源/MCP 相对于强编码 agent 的贡献 |
| **Claude + Repo (Sonnet 4.6)** | 模型版本混淆 |
| **Biomni**（API，因成本排除于 100 篇基准） | 通用生物医学 agent |
| **Claude browser-use**（直接读论文 URL） | 结构化资源 vs 原始网页阅读 |
| **Human researchers** | 可复现性 ground truth |
| **Ablations**（见下） | 内部模块贡献 |

**原文没有**：raw-LLM / 无上下文基线、generic-wrapper 基线、Code2Skill 头对头。这些是本研究的**补充基线**（B0/B1/B2/B3），不是与原文一一对应。

### Ablation（原文 5 变体，均在 AlphaGenome，30 题，claude-sonnet-4-20250514）
1. Monolithic agent（单 200k 上下文，无分解）
2. Non-parallel multi-agent（强制顺序）
3. No test verifier–improver
4. **Markdown skill files**（MCP 工具替换为 Claude Code Skills 文本技能）
5. Alternative scaffolding（OpenCode）

> **重要**：主文**没有给出数值消融结果**（仅说“自动化验证与多 agent 设计有贡献”，详见 Supplement）。变体 4 对模型最相关——作者自己已测试非可执行文本技能表示，但主文无数字。

### Robustness / 故障注入（原文）
- 3 个仓库（**AlphaGenome** 笔记本、**POP-TOOLS** CLI、**mlearner** R CLI）× 4 类错误 = **12 个对抗配置**，注入在运行前且**不告知 agent**：
  1. Missing dependencies（移除必需包）
  2. Broken file paths（改写路径为不存在）
  3. Typographical errors（拼写错误函数/包/变量名）
  4. Deprecated API calls（替换为废弃/不兼容调用）
- 记录：是否**检测到**、**修复策略**、修复后是否**通过全部验证**。主文结论为**定性**（“恢复了 functional MCP server”），**无检测率/修复率/拒绝率数字**（在 Supplement）。
- 越界拒绝（permuted paper–question 基准）：**100% 正确拒绝**越界查询（带/不带拒绝指令未区分）；
- 无 tutorial 消融、prompt 改写鲁棒性、shortcut-learning 探针（手动 + 自动化审查 agent）。

### 统计
- 点估计：bootstrap 的 **± s.e.m.**；
- 配对检验：**paired t-test（每运行准确率）**；
- 大规模（100 篇）：**bootstrap 假设检验（10,000 resamples），报告准确率差值的 95% CI**；
- 人类评分：**96.7% 评分者一致性**；
- 发现案例：Spearman ρ + 双侧 P + Benjamini–Hochberg（FDR<0.05）；
- **未做按论文聚类**（尽管有 100 篇语料）；
- **警告**：开放式任务“基于与单一参考一致的基准”应主要解释为忠实执行而非分析有效性；开放式科学推理仍 human-in-the-loop。

### 指标清单（原文）
正确率（tutorial/novel/open-ended/synthesis/execution）、评分者一致性、**agentification 成功率（74/100）**、**工具验证通过率（593/599）**、越界拒绝率、可复现一致性、生物一致性、构建耗时/成本、每查询成本/延迟、相对加速、运行时间分布、故障检测/修复/一致性、消融 delta、每论文工具数、失败模式分类。

---

## 2. Model2Agent 对应实验

| Paper2Agent | Model2Agent 对应 | 是否可直接比较 |
|-------------|------------------|----------------|
| 六阶段流水线 | AGCI 扫描 → 能力归纳 → MCG → 统一 Agent 生成 → 参考推理验证+修复 | 阶段结构对应；**实现不同**（模型资产 vs 论文） |
| 100 篇论文端到端 | 100 个模型端到端（10 家族 × 10） | 规模对应，对象不同 |
| 300 tutorial 题 | 300 tutorial-derived 题（模型示例衍生） | 结构对应 |
| AlphaGenome novel | 300 novel 题（未见输入/新参数组合） | 结构对应 |
| 30 open-ended | 3 代表模型 × 30 = 90 open-ended | 结构对应 |
| 26 篇综合 / 10 非生物 | 30 未见任务家族（跨域泛化） | 结构对应 |
| 故障注入 12 配置 | 6 类故障 × 若干（含模型特有 2 类） | 结构对应，扩 2 类 |
| 消融 5 变体 | A1–A5（见 §7） | 结构对应 |
| Claude+Repo 基线 | B0（DeepSeek + 原始资产） | **本研究强基线** |
| ——（原文缺） | B1 通用封装 / B2 直接生成 / B3 相关研究 | 补充基线 |
| 越界拒绝 | 不安全修复拒绝率 | 对应 |

---

## 3. 因输入不同而必须修改的设计

1. **验证锚点**：Paper2Agent 用 tutorial 执行 gold standard；Model2Agent 用**原始模型参考推理**（同一权重、同一函数、同一输入）。原因：模型无“tutorial 文档”，输出不像代码有确定性文本。
2. **容忍判据复用**：沿用 3% 浮点容差（标量预测精确匹配；概率向量按类容差 1e-6，因同权重确定性）。
3. **失败模式扩类**：在 Paper2Agent 的 4 软件故障之上，增加 **预处理漂移** 与 **权重-配置不匹配** 两类模型特有故障。
4. **Baseline 补齐**：原文无 raw/generic-wrapper 基线；B0/B1/B2/B3 为本研究补齐，公平声明见 §4。
5. **MCP→Skills**：不引入 MCP；Skills 仅作为单体应用内的路由机制，**不主张为方法创新**（因 Paper2Agent 仓库已用 Skills）。
6. **图数对齐**：Figure 1–4 严格对应论文叙事；Figure 5 为可选深入案例，缺数据仅出模板。

---

## 4. 实验指标与评价单位

| 指标 | 单位 | 评价口径 |
|------|------|----------|
| End-to-end Agentification Success Rate | %（分母=所有尝试模型，含失败转换） | 同时满足：构建环境、加载正确权重、生成独立 Agent、通过参考推理验证、完成≥1 保留下游任务、从导出包重启成功 |
| Tool / Capability Verification Rate | %（分母=可验证能力数；无示例的能力记为未验证，不计入失败） | 参考推理 vs 实际执行的精确/容差匹配 |
| Tutorial Task Accuracy | % | 模型示例衍生题的正确率 |
| Novel Task Accuracy | % | 未见输入/新组合的正确率 |
| Open-ended Task Success | %（Rubric，2 评估者 + 评分者一致性） | 多步规划、多能力调用、结果综合 |
| Behavioral Fidelity | 距离/相关系数 | agent 输出 vs 参考推理分布一致性 |
| Unsupported Capability Rate | % | 请求超出资产能力且被正确拒绝的比例 |
| Generation Cost and Time | USD / 秒 | 转换阶段 LLM 花费与耗时 |
| Query Cost and Latency | USD / 毫秒 | 每查询 LLM 花费与延迟 |
| Manual Intervention Count | 次 | 需人工介入的次数 |

**禁止**：将静默错误的模型输出视为成功（对齐 Paper2Agent 的“排除失败工具”而非静默保留）。

---

## 5. 不可直接比较的结果与原因

1. **Paper2Agent 91.2% tutorial 准确率**：**不可**与 Model2Agent 同方法百分比直接统计比较。原因：语料（论文 vs 模型）、底层模型（Claude Sonnet 4 vs DeepSeek）、工具/环境均不同。论文中仅作为背景引用；真实性能比较必须在**相同任务与运行条件**下重新执行。
2. **74/100 agentification 成功率**：仅作规模参照；分母构成不同（论文 vs 模型资产，失败模式不同：缺代码 vs 缺权重/权限）。
3. **593/599 工具验证通过率**：结构类比到 capability verification rate，但工具粒度不同（MCP 工具 vs 模型能力）。
4. **消融/鲁棒性数字**：原文仅在 Supplement 有数值；主文无，故不可直接引用具体检测率/修复率。
5. **底层模型预训练覆盖**：DeepSeek 可能预训练见过部分目标模型；**“未见家族”**指对 Model2Agent 的研发/调参过程保留，不保证底层 LLM 从未见过该模型——需在论文中明确声明。

---

## 6. 模型/方法冻结与公平性

- 方法冻结（P2 完成）后运行未见家族测试；测试期间**不允许**为该家族新增专用 Skill 或修复规则。
- B0/B1/B2/B3/M 共享：**同一 LLM（DeepSeek v4.1-flash）、同一资产、同一任务、同一计算资源与调用预算**。
- B3（Paper2Agent/Code2Skill）仅在“输入条件适用的子集”运行：即具备对应论文/代码仓库的模型；**不可强行**让其处理纯权重目录，并记录输入条件。
- 不伪造结果、不通过弱化基线获得优势；不能公平运行的基线记录明确原因。

---

## 7. Model2Agent 消融设计（A1–A5）

| 消融 | 删除/修改 | 回答的问题 |
|------|-----------|------------|
| A1 No MCG | 不生成显式模型能力图 | MCG 是否必要 |
| A2 No Reference Execution | 不运行原始推理建立执行证据 | 真实模型执行证据的贡献 |
| A3 No Verification & Repair | 不进行自动测试与修复 | 验证闭环是否影响可靠性 |
| A4 Static Skill Routing | 固定顺序执行 Skills | 动态能力路由是否有效 |
| A5 No Model-specific Semantics | 仅基于代码函数生成工具 | **模型语义归纳是否有独立贡献**（最关键） |

> 若 A5 与完整方法无显著差异，则 AGCI 强调的模型语义归纳缺乏实证必要性——这是本研究必须正面回答的内部效度问题。

---

## 8. Robustness 故障注入设计（对齐 + 扩展）

| 故障类型 | 示例 | 对齐原文 |
|----------|------|----------|
| Missing Dependencies | 删除一个必需依赖 | ✓ 对应 missing dependencies |
| Broken Paths | 修改权重/配置路径 | ✓ 对应 broken file paths |
| Deprecated APIs | 调用已变更的加载接口 | ✓ 对应 deprecated API |
| Invalid Input Schema | 交换特征顺序 / 错误数据类型 | ✓ 对应 typographical/结构错误 |
| Preprocessing Drift | 修改图像归一化参数 | ✗ 模型特有（扩展） |
| Weight-Configuration Mismatch | 错误标签映射 / 模型结构版本 | ✗ 模型特有（扩展） |

**报告指标**：故障检测率、自动修复成功率、修复后输出一致性、不安全修复拒绝率。
**关键约束**：验证指标不能仅是“程序是否恢复运行”；必须区分“修复后输出是否与原始模型一致”以及“能否识别不可安全修复的模型语义错误并拒绝继续执行”。

---

## 9. 统计与复现要求

- 保存每个模型、每个任务、每次重复的**原始记录**（JSONL）。
- 配对分析主方法与基线（paired t-test on per-run accuracy）。
- 相关任务用**模型级聚类 Bootstrap** 计算 95% CI（不依赖单一 P 值判断优劣）。
- 仅 2 个模型的 Pilot：仅报告**描述性结果**，不宣称跨模型泛化。
- 复现记录：Git commit、模型 revision/hash、prompt 与 skill 版本、Claude Agent SDK 版本、DeepSeek 模型 ID、Python/依赖版本、随机种子、运行环境/GPU、原始执行轨迹、每次调用成本与耗时。
- 禁止记录密钥或私有 LLM 思维链（本项目已通过 `.env` + scrub 实现）。

---

*本对齐文档随实验推进（P0→P4）持续更新；当前处于 P0（2 模型技术可行性）阶段。*
