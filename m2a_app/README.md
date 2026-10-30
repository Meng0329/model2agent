# Model2Agent V1.0 — AI Native 产品

把「已有机器学习模型」通过自然语言转换为**独立、可交互、可运行、可下载、可部署**的 Agent 应用。

## 唯一 Agent 运行底座：Claude Agent SDK

- `m2a_app/agent.py`：`ClaudeSDKClient` 连续会话 + `StreamEvent` 流式 + 真实工具卡片 + `interrupt()`。
- 无 OpenAI 回退、无自研 Agent Loop、无关键词路由、无伪造工具事件。
- LLM 为 DeepSeek（Anthropic 兼容网关 `ANTHROPIC_BASE_URL`，`CLAUDE_CODE_ALLOW_OTHER_MODELS=1`）。
- `setting_sources=["project"]`：只加载项目 `.claude/skills`，隔离用户全局 CLAUDE.md。

## 已验证（真实执行）

| 项 | 结果 |
|---|---|
| SDK 连续对话 | 3+ 轮（`connect`/`query`/`receive_response`） |
| 真实工具 | Write 创建文件、Read 读回 |
| Skills | `ping` 技能被 `Skill` 工具真实调用返回 PONG-SKILL |
| 流式 | StreamEvent text_delta 增量渲染（无重复） |
| 中断 | `interrupt()` 12s 内终止 |
| 端到端生成 | 主 Agent 读取 CNN 资产→写 `INSPECTION.md`→生成 `execute_model.py` |
| 设备检测 | 2× RTX A6000（torch.cuda + nvidia-smi，真实） |
| UI | Gradio 6.31 三栏，HTTP 200，54 组件 |

## 运行

```bash
python3 -m m2a_app.app          # 默认 http://127.0.0.1:7861
M2A_PORT=7862 python3 -m m2a_app.app
```

## 结构

```
m2a_app/
  config.py     环境与路径（密钥仅 .env）
  devices.py    真实 GPU/CPU 检测
  store.py      任务/设备/会话持久化（JSON 文件）
  workspace.py  每任务隔离工作空间 + 安全路径 + ZIP
  agent.py      Claude Agent SDK 会话桥（唯一运行时）
  preview.py    生成 Agent 独立进程预览生命周期
  app.py        Gradio 三栏 UI（左历史/中对话/右工作空间）
  skills/       model-inspection / model-execution / agent-generation /
                gradio-ui-generation / agent-testing / docker-packaging
```
