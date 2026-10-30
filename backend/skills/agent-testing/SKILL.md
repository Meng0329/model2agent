---
name: agent-testing
description: 对生成的 Model Agent 做真实测试：权重自检、自身 SDK 会话、FastAPI 启动与真实推理。在报告成功前使用。
---
# Agent 测试

对生成的 Agent 做端到端真实验证：
1. 调用 MCP 工具 **`verify_agent`**，参数 `{"task_id": "<当前任务ID>"}` → 启动生成体的 FastAPI、探活 `/api/health`、读 `/api/config`、运行 `model_exec.selfcheck()`（每个能力真实预测，严禁虚构）。
2. 确认生成体 `agent_core` 的 SDK 会话能作答并调用 `run_model`（真实权重）。

失败必须如实报告（verbatim）。**未测试或失败的运行绝不标记为成功。**
