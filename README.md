# Model2Agent V0.3 — Paper2Agent-Aligned Model-Agent Research Framework

> 将异构**已训练模型资产**自动转化为经验证、可独立运行的 Agent，并复刻 Nature 2026 Paper2Agent 的
> 证据链（端到端成功率、工具/能力验证率、tutorial/novel/open-ended 准确率、鲁棒性、统计推断）。
> 见 [`docs/paper2agent_alignment.md`](docs/paper2agent_alignment.md)。

## 固定技术栈
Python · Claude Agent SDK · DeepSeek API（外部 LLM 路由）· Gradio · PyTorch / Transformers / sklearn / XGBoost · pytest · pandas · JSONL。
单体应用 + Skills 路由（**Skills 仅作内部路由机制，非方法创新**——Paper2Agent 仓库已用 Skills+MCP）。

## 核心方法
1. **AGCI（Asset-Grounded Capability Induction，资产锚定能力归纳）**：扫描模型资产 → 发现推理入口、权重、I/O Schema、约束、可执行来源证据。
2. **MCG（Model Capability Graph，模型能力图）**：以归纳出的能力为节点、组合依赖为边。
3. **统一 Agent 构建**：单一模板按 MCG 生成独立 Model Agent（**不为每个测试模型手写 Agent 代码**）。
4. **参考推理验证与修复**：以原始模型真实执行作为 ground truth（3% 浮点容差 / 概率 1e-6 容差），失败能力不计入成功。

## 快速开始
```bash
pip install -r requirements.txt        # 需 PEP668 时加 --break-system-packages
cp .env.example .env                    # 填入 DEEPSEEK_API_KEY（.env 已被 .gitignore，绝不上库）
export CUDA_VISIBLE_DEVICES=0           # 本机仅用 GPU0（用户约束）
python model_assets/<slug>/train.py     # 训练并冻结 pilot 权重（cnn_digits / xgb_tabular 已预训练）
python scripts/freeze_tasks.py          # 冻结 benchmark 任务 + ground truth（参考推理）
python scripts/run_pilot.py --reps 5 --methods B0 B2 M   # 2 模型端到端实验
python scripts/run_analysis.py          # 配对检验 + 聚类 Bootstrap 95% CI
python scripts/run_robustness.py        # 6 类故障注入
python scripts/make_figures.py          # Figure 1-5（缺数据仅出模板，不造假）
pytest tests/                           # 核心单测（含密钥泄漏检查）
```

## 目录
```
model_assets/<slug>/   # 模型资产：manifest.json, infer.py(真实推理入口), 模型卡, 示例, 训练脚本
model2agent/agci/      # 资产扫描 + 能力归纳
model2agent/mcg/       # 模型能力图
model2agent/builder/   # 统一 Agent 生成（含 Gradio/CLI 启动器）
model2agent/verification/  # 参考执行 oracle + 比对
model2agent/benchmark/     # 任务 Schema / 运行器 / 指标
model2agent/baselines/     # B0(B0_raw_assets) B2(B2_direct_synthesis) + 预留 B1/B3
model2agent/robustness/    # 故障注入
model2agent/stats/         # 配对检验 / 聚类 Bootstrap / 效应量
model2agent/skills/        # 内部路由注册表（非创新）
generated_agents/<slug>/   # 生成的独立 Agent（由只读生成）
results/                   # frozen/ logs/ csv/ figures/
```

## 指标与公平性
见 `docs/paper2agent_alignment.md`。所有方法与主方法共享同一 LLM（DeepSeek v4.1-flash）、
同一资产、同一任务、同一预算。失败转换计入端到端成功率分母。静默错误输出**不**视为成功。

## 2 模型 Pilot（P0）已交付
- 模型：**cnn_digits**（PyTorch CNN，GPU0）、**xgb_tabular**（XGBoost）。
- 方法：M（完整）、B0（DeepSeek+原始资产）、B2（直接生成）。
- 产出：可运行代码、原始 JSONL、`summary.csv`、`analysis.json`、Figure 1-5（数据缺失处仅模板）。

## 复现与失败报告
复现信息（commit / 模型 hash / 依赖版本 / 随机种子 / GPU / 成本耗时）写入 `results/logs/`。
**未执行的实验（100 模型 / 消融 / 未见家族）一律标记为未完成，不伪造成果。**
