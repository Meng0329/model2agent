---
name: agent-generation
description: 生成独立 Model Agent 项目（独立 SDK 运行时 + DeepSeek + React UI + 模型推理 + Dockerfile）。在模型被检查并真实执行后使用。
---
# Agent 生成

用确定性生成工具在 `project/` 产出完整、可独立运行的 Agent 项目。

## 步骤
1. 确定资产目录：上传的 bundle 在 `inputs/` 下（若为 ZIP 已解压到 `inputs/<slug>/`）。
2. 调用 MCP 工具 **`generate_agent`**，参数：`{"task_id": "<当前任务ID>", "asset_dir": "inputs/<slug>"}`。
   该工具在 Builder 进程内执行确定性生成（非 LLM 文本）：复制 React+FastAPI 模板、把**真实权重**复制进
   `project/assets/<slug>/`、依据资产 manifest+examples 写出 `project/config.json`
   （input_type / capabilities / adapters / feature_names / labels）。

## 规则
- **绝不允许凭模型名猜测能力**——一切来自 manifest + examples + 真实入口。
- 若 `generate_agent` 返回 ERROR，必须如实报告，不得标记成功。
- 生成后调用 `verify_agent`（真实权重加载 + 每个能力真实执行 + 启动探活）。
