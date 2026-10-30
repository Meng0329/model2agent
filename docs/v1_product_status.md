# Model2Agent V1.0 产品开发状态（真实执行，非声称）

## 已完成（已真实测试）

- **Phase 0 修正 Agent Runtime**：Claude Agent SDK 为唯一底座，DeepSeek Anthropic 兼容接入。
  8 项 Smoke 全部通过：回复、连续多轮、真实读文件、真实写文件、Skills 发现与调用、
  流式增量、工具结果续规划、中断。无 OpenAI 回退。
- **Phase 1 任务与设备**：设备配置弹窗（真实检测 2× RTX A6000，仅一次）；新建任务表单；
  任务历史与工作空间持久化（JSON 文件）；表单提交生成首条任务消息并提交 SDK 会话。
- **Phase 2 三栏 UI**：Gradio 6.31，左任务历史 / 中真实流式 Agent 对话 + 工具卡片 + 停止 /
  右文件工作空间（FileExplorer + 代码预览）+ 预览与下载入口。已启动 HTTP 200、54 组件。
- **Phase 3（部分）**：主 Agent 用真实工具读取 CNN 资产、执行 model-inspection、
  生成 `project/INSPECTION.md` 与 `project/scripts/execute_model.py`（真执行模型，含 __pycache__）。

## 未完成 / 已知缺口（如实列出，不标记完成）

- Phase 3 剩余：生成的**独立 Agent** 需自身 SDK Runtime + Gradio UI + 独立会话（尚未生成并自测）。
- Phase 4 真实预览：`preview.py` 已写（独立进程/真实端口/HTTP 探活），但未用真实生成项目验证。
- Phase 5 Docker ZIP：skill 与 export 已写，Docker 构建未验证（默认「未验证」）。
- Phase 6 UI 打磨：右侧栏按钮偏挤、聊天区默认过高；需逐页走查。
- 全部 6 界面（新建表单/设备弹窗/三栏/工作空间/预览/导出）尚未逐一视觉验收。

## 已知技术要点

- `CLAUDE_CODE_ALLOW_OTHER_MODELS=1` + `ANTHROPIC_BASE_URL`(网关) + `model=deepseek-v4.1-flash`
  是 CLI 与网关模型名的兼容关键。
- `setting_sources=["project"]` 隔离用户全局 CLAUDE.md 且不破坏技能发现。
- `connect("")` 会被当作空用户消息——无首条提示时不传 prompt。
- 内置工具结果经 `UserMessage` 的 `ToolResultBlock` 返回（非 AssistantMessage），已处理。
- 端口 7860 被本机其它应用占用，产品默认用 7861（可用 `M2A_PORT` 改）。
