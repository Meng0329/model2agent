# Model2Agent: 将已训练/微调模型转化为交互式 AI Agent

**文档用途**：实验与论文写作启动前的 idea 整理  
**日期**：2026-10-29  
**状态**：文献调研与 novelty 初步确认完成，待进入方法设计与实验阶段

---

## 1. 核心 Idea

**Model2Agent**：模仿 Paper2Agent 的思路，自动把**已训练或微调好的模型**（权重文件 + 推理代码 + 模型卡 + 示例输入输出 + 相关配置）转化为经过验证的交互式 AI Agent。

最终形态预期为：
- 基于 MCP（Model Context Protocol）或兼容协议的可调用服务
- 支持自然语言查询
- 可执行模型推理、解释、不确定性估计、轻量适配等操作
- 经过自动化测试与验证，具备一定可靠性
- 可与其他 paper agent / model agent 组合协作

**目标**：降低科学模型的复用门槛，让模型从“静态权重 + 说明书”变成可交互、可执行、可协作的科学工具。

---

## 2. 最接近的相关文献

### 2.1 Paper2Agent（最直接对标）

- **论文**：*Reimagining Research Papers As Interactive and Reliable AI Agents*
- **作者**：Jiacheng Miao, Joe R. Davis, Yaohui Zhang, Jonathan K. Pritchard, James Zou
- **发表**：Nature, 2026（arXiv:2509.06917）
- **核心方法**：多 agent 系统分析论文 + 代码库 → 抽取工具 → 构建 MCP server → 自动生成并运行测试进行验证 → 连接 chat agent，成为“虚拟通讯作者”
- **关键结果**：100 篇计算生物论文中成功 agent 化 74 篇；生成 599 个工具，593 个通过验证
- **边界**：以**论文及其代码库**为中心。模型只是论文中的一个组件（如 AlphaGenome），并非以“已训练模型本身”为独立输入对象。验证主要基于代码执行与 tutorial 复现。

### 2.2 Code2MCP

- **论文**：*Code2MCP: Transforming Code Repositories into MCP Services*
- **作者**：Chaoqian Ouyang et al.
- **发表**：arXiv:2509.05941（后相关工作发表于 KDD 系列）
- **核心方法**：七个专用 agent（Download、Environment、Analysis、Generation、Run、Review、Finalize）+ Run-Review-Fix 自校正循环。输入任意 GitHub 仓库 URL，输出可部署的 MCP service。
- **关键结果**：50 个跨领域科学仓库，约 64% 完全成功；库风格项目表现更好。
- **边界**：面向**通用代码仓库**。模型若存在于仓库中会被当作普通代码处理，但不专门处理预训练权重、模型卡、推理接口或模型特有验证。

### 2.3 Model Cards + MCP

- **论文**：*AI/ML Model Cards in Edge AI Cyberinfrastructure: towards Agentic AI*
- **作者**：Beth Plale et al.
- **发表**：arXiv:2511.21661
- **核心内容**：把模型卡做成动态对象，并评估用 MCP 作为接口（对比 REST）。
- **边界**：聚焦模型卡作为可查询/可订阅的**元数据对象**，而非把模型本身转化为可执行的预测/解释/适配 agent。

### 2.4 其他相关但方向不同的工作

| 工作 | 方向 | 备注 |
|------|------|------|
| agent2model | Agent → 模型权重 | 反向工作，把工作流编译进模型 |
| AutoMCP | OpenAPI → MCP | 针对 REST API，不是模型 |
| Agent Cards | 文档标准 | 描述 agent 的元数据，不是从模型生成 agent |
| Agentic Science 综述（arXiv:2508.14111） | 宏观框架 | 定位 Agentic Science 为 AI4S 的下一阶段 |
| Nature Reviews Methods Primers (2026) | 综述/Primer | Agentic AI 作为实验室“计算大脑” |

---

## 3. Novelty 分析

### 3.1 与现有工作的真实差异

| 维度 | Paper2Agent / Code2MCP | Model2Agent（拟） |
|------|------------------------|-------------------|
| **核心输入** | 论文 + 代码库 / 任意 GitHub 仓库 | 已训练模型（权重 + 模型卡 + 推理代码 + 示例） |
| **工具设计** | 从代码/tutorial 中抽取通用函数 | 针对模型特有操作：预测、解释、不确定性、轻量适配 |
| **验证重点** | 代码可运行 + tutorial 复现 | 代码可运行 + 模型输出一致性、扰动测试、失败模式检测 |
| **生命周期** | 一次性转化 | 可扩展到版本管理、在线轻量适配、与其他 agent 组合 |

### 3.2 Novelty 陈述（可直接用于论文引言）

> 现有工作（Paper2Agent、Code2MCP）已证明可以自动将论文或代码仓库转化为经过验证的 MCP agent。然而，在 AI for Science 中，大量关键贡献以**训练好的模型**形式存在，而非可直接运行的分析脚本。这些模型面临权重加载、环境依赖、输入输出规范、可信度评估等额外障碍。Model2Agent 提出以“已训练模型”为一级公民的自动化流水线，专门解决模型资产的工具抽取、接口标准化与输出验证问题，从而把科学模型从静态资产转化为可交互、可协作的 agent。这一方向与现有 paper/repo 中心化的方法在问题设定和验证机制上存在实质性差异。

**结论**：与 Paper2Agent 和 Code2MCP 在技术模式上有表面相似，但在核心问题、关键方法和贡献边界上并不高度重合，具备可信的 novelty。

---

## 4. 领域关键问题与缺口（与本 idea 相关）

1. **验证闭环困难**：模型输出不像代码有明确“标准答案”，缺乏自动验证机制。
2. **软件与模型债**：大量模型缺乏完整模型卡、示例代码或可复现环境。
3. **接口不标准**：模型推理接口、输入输出 schema 高度异构。
4. **不确定性与失败模式**：现有 agent 化工作几乎不处理模型预测的不确定性与失败检测。
5. **生态整合不足**：模型难以与 paper agent、实验 agent 无缝组合。

**Model2Agent 可贡献的点**：
- 专门的模型验证流水线（一致性、扰动、基准对比）
- 从模型卡 + 示例自动生成标准化工具接口
- 推动“模型可用性”（model availability）成为类似 code/data availability 的发布标准

---

## 5. 建议的下一步

### 5.1 短期（方法设计）
- 明确输入规范：最小可行输入是什么？（权重路径 + 模型卡 + 推理脚本？还是 Hugging Face model ID？）
- 设计工具抽取规则：哪些模型操作值得自动暴露？（predict、explain、uncertainty、adapt 等）
- 设计验证策略：如何在没有“标准答案”的情况下判断模型 agent 是否可靠？

### 5.2 中期（实验）
- 选择 2–3 个有代表性的科学模型做 case study（建议：蛋白质模型、材料势函数、或基因组模型）
- 对比基线：直接用 Claude + 原始代码 vs Model2Agent 生成的 agent
- 指标：工具生成成功率、验证通过率、查询准确率、使用成本与时间

### 5.3 写作注意点
- 引言中明确对比 Paper2Agent 和 Code2MCP
- 强调“模型特有问题”而非泛泛的 agent 化
- 讨论失败模式与局限性（类似 Paper2Agent 报告的 26% 失败率）

---

## 6. 必读文献清单（优先级）

**必读**
1. Paper2Agent（Nature 2026 / arXiv:2509.06917）
2. Code2MCP（arXiv:2509.05941）
3. *From AI for Science to Agentic Science*（arXiv:2508.14111）
4. *Agentic AI systems for scientific discovery*（Nature Reviews Methods Primers, 2026）

**推荐**
5. Model Cards + MCP（arXiv:2511.21661）
6. Agent4Sci（arXiv:2610.28763）——了解当前 agent 在科学模型改进上的局限
7. Agentic AI Scientists 位置论文（arXiv:2605.08956）——验证与自主性挑战

---

**文档结束**  
本文件可作为实验设计与论文写作的起点。建议在开始实现前先确定 1–2 个具体模型作为 pilot。
