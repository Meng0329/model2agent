# Model2Agent V2.0 — 代码审计与模块处置结论

> 审计时间：2026-10-30 · 审计对象：`/data/mzb/paper2agent`（main 分支）
> 目的：为 V2.0（React + FastAPI 重建）确定哪些模块保留 / 重构 / 替换 / 删除。

## 一、环境审计（真实只读检查）

| 项 | 结果 | 阻塞？ |
|---|---|---|
| Python | 3.12.3（系统） | 否 |
| claude-agent-sdk | **0.2.170**（真实，非 mock） | 否 |
| fastapi | 0.134（**无 `fastapi.sse`**，用 StreamingResponse） | 否 |
| torch | 2.10.0+cu128，CUDA **可用** | 否 |
| GPU | 2× RTX A6000，48GB，37GB+24GB 空闲 | 否 |
| Docker | 守护进程运行中，nvidia-ctk 1.18.2 | 否 |
| Node | v24.16 + npm 11 | 否 |
| Playwright | 1.64.1 + Chromium 已缓存（多版本） | 否 |
| transformers | **未安装**（仅影响 bert_zh） | 仅 bert_zh 受阻 |
| DeepSeek Key | **最小化真实请求 200 AUTH_OK**（inferaiapi 网关 /v1/messages，deepseek-v4.1-flash） | 已清除 |
| 磁盘 | 226G 剩余 / 94% 占用 | 留意 headroom |

## 二、模块处置

### KEEP（保留并迁入 backend/，最小改动）

- **`m2a_app/agent.py` → `backend/agent_bridge.py`**：真实 Claude Agent SDK 运行时。
  - 真实 `ClaudeSDKClient`、`include_partial_messages=True`、`StreamEvent` 文本/工具增量解析（`content_block_delta`→`text_delta`）。
  - 按任务的 `SessionManager`，真实 `interrupt()`，真实 `resume=session_id`。
  - 暴露 `respond(prompt)→async dict` 事件流；保留 `start_preview`/`stop_preview` MCP 工具。
- **`m2a_app/config.py` → `backend/config.py`**：环境变量驱动的 DeepSeek Anthropic 兼容端点，无硬编码密钥/Provider 回退。新增 `V2_GENERATED_ROOT`。
- **`m2a_app/devices.py` → `backend/devices.py`**：真实 `nvidia-smi` + `torch.cuda` 遍历全部 GPU，报告真实显存；尊重所选设备（修正 V1 硬编码 GPU0）。
- **`m2a_app/workspace.py` → `backend/workspace.py`**：隔离目录 + 路径穿越防护 + 安全解压 + 项目专用导出（排除 `.env` 等）；新增 `watch()`（watchdog）→ `workspace_changed`。
- **`m2a_app/preview.py` → `backend/preview.py`**：真实子进程 + HTTP 探活 + 生命周期；改用 `proc.terminate()`；新增 `stop_all()` 与孤儿回收；传入所选 `CUDA_VISIBLE_DEVICES`。
- **`m2a_app/generator.py` → `backend/generator.py`**：模板复制 + 真实资产分析（importlib 发现可调用入口、从 examples 推测输入类型、真实向量长度）+ 真实权重复制。扩展为产出 React+FastAPI 项目。
- **`m2a_app/skills/*` → `backend/skills/`**：6 个真实 SKILL.md（model-inspection / model-execution / agent-generation / gradio-ui-generation → 改为 react-ui-generation / agent-testing / docker-packaging）。纯指令型技能补验证脚本。

### REFACTOR

- **`m2a_app/store.py` → `backend/db.py`**：JSON 文件全量重写、无并发控制 → SQLite（`tasks`、`messages`、`settings`、运行账本）。

### DELETE / REPLACE

- **`m2a_app/app.py`（Gradio 401 行单体）**：删除，由 `backend/app.py`（FastAPI）+ `frontend/`（React）取代。
- **`m2a_app/templates/generated_agent/`（Gradio）** → **`generated_agent_template/`**（React 聊天 + FastAPI + model_exec + Dockerfile）。

## 三、模型资产结论

| 资产 | 框架 | 输入 | 权重 | 真值 | 端到端可用性 |
|---|---|---|---|---|---|
| cnn_digits | pytorch | 8×8→64 维向量（值域 0–16） | cnn_state.pt（真实） | **有** | ✅ 核心图像测试标的（适配上传图→缩放灰度→展平） |
| xgb_tabular | xgboost | 30 维（乳腺癌 schema） | model.json（真实） | **有** | ✅ 核心表格测试标的（CSV 上传→批量预测） |
| sklearn_digits | sklearn | 64 维向量 | model.joblib（真实） | 无 | ⚠️ 仅推理，无标注 |
| bert_zh | transformers | 文本 | 无权重文件（依赖 HF 缓存） | 无 | ⛔ 排除（缺 transformers + 不可移植） |

## 四、关键决策

1. **直接改造，不保留并行 V1/V2 目录**；在 `main` 上开发（用户明确授权）。
2. 完整 7 阶段，每阶段真实验收门禁；严禁 Mock 冒充通过。
3. Generated Agent 用 React UI（复用 ChatGPT 式外壳）。
4. 图像测试适配 cnn_digits；真实图片上传 → 缩放到 8×8 灰度 → /16 → 展平 64 → 真实推理；如实标注自然照片上的局限。
5. Docker 验证由 `V2_DOCKER=1` 门控，否则状态 `unverified`，绝不虚报。
