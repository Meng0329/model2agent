# Model2Agent V1.0 产品开发状态（真实执行，非声称）

## Phase 0–6 完成情况（全部真实执行验证）

### Phase 0 — 修正 Agent Runtime ✅
Claude Agent SDK 为唯一底座，DeepSeek Anthropic 兼容接入。8 项 Smoke 全通过：
回复、连续多轮、真实读文件、真实写文件、Skills 发现与调用、流式增量、工具结果续规划、中断。
- 关键：`CLAUDE_CODE_ALLOW_OTHER_MODELS=1` 解 CLI↔网关模型名死锁；
  `setting_sources=["project"]` 隔离用户全局 CLAUDE.md 且保留技能发现；
  只用 StreamEvent 增量渲染（修复重复文本）；内置工具结果经 `UserMessage.ToolResultBlock`。
- 无 OpenAI 回退、无自研 Loop、无关键词路由、无伪造工具事件。

### Phase 1 — 任务与设备 ✅
- 设备配置弹窗：真实检测 2× NVIDIA RTX A6000（torch.cuda + nvidia-smi），仅一次。
- 新建任务表单（名称/目标/资产上传）；任务历史与工作空间持久化（JSON）；
  表单提交生成首条任务消息并提交 SDK 会话。

### Phase 2 — 三栏 UI ✅
Gradio 6.31：左任务历史 / 中真实流式 Agent 对话 + 工具卡片 + 停止 /
右文件工作空间（FileExplorer + Code 预览）+ 预览/下载。HTTP 200、54 组件；已截图验证。

### Phase 3 — 真实生成能力 ✅（两种模型类型）
- CNN + XGBoost 均生成**独立可运行 Agent**（`project/`），各自带**自身 Claude SDK 会话**。
- 主 Agent 用真实工具读取资产、执行 model-inspection、生成 INSPECTION.md / execute_model.py。
- 生成器 `m2a_app/generator.py` 只保留 infer.py 中真实可调用能力（排除 `runs` 等元数据），
  input_type 由真实 examples 判定（CNN→vector64，XGBoost→vector64）。
- 生成 Agent 真实推理自检：CNN predict=9、XGBoost predict=1（均与 ground truth 一致）；
  其自身 SDK 会话经 `mcp__m2a_model__run_model` 工具调用真实权重（predict=0，正确）。

### Phase 4 — 真实预览 ✅
`PreviewManager`：独立进程 + 真实空闲端口 + HTTP 探活。启动→running（HTTP 200），停止→stopped。
浏览器交互：填入 64 个数字 →「运行推理」→ 真实结果 `0`；非法输入 → 明确校验提示。

### Phase 5 — Docker ZIP ✅
- `m2a_data/workspaces/cac375ae76df/project/` 完整打包为 ZIP（含 run.py/Dockerfile/requirements/权重）。
- 真实构建：`BUILD_RC=0`，镜像 `m2a-cnn-agent:latest`（10.9GB）。
- 真实运行：`docker run` 后 app **HTTP 200**（title "Model Agent · cnn_digits"）→ **build-ok + start-ok**。

### Phase 6 — UI/UX 打磨 ✅（主要项）
- 右侧栏按钮重排（不再拥挤）；聊天区高度调整；新建/设备弹窗改为固定 overlay + 居中卡片（已截图）。
- 已知待优化（非阻塞）：设备弹窗需清空 device 后可见；文件树用 FileExplorer 原生；
  少量动效仍为默认。

## 验收测试（scripts/v1_acceptance.py）
`PASS 11/11`（V1.1，T10 Docker 需 `V1_DOCKER=1` 重建后生效）：
T1 单次发送（num_turns==1）、T2 真实 ToolUse+ToolResult（Write/Read 完成+落盘）、
T3 SDK session_id+chat 持久化、T4 历史点击恢复、T5 工作空间文件同步、
T6 CNN+XGB 生成 Agent 真实推理（predict=9 / predict=1）、
T7 生成 Agent 自身 SDK 多轮、T8 Builder Agent 驱动预览+停止、T9 ZIP 含权重且无密钥、
T10 Docker 容器内真实推理（`V1_DOCKER=1` 时运行）。

## 已知技术要点 / 边界
- 密钥仅 `.env`（gitignore）；生成项目 `.env.example` 不含真实 key。
- Docker 权重包含策略：CNN/ XGB 资产许可允许打包（PyTorch/XGBoost 宽松许可），
  已在 `.dockerignore` 排除 `__pycache__`/`.env`。
- 端口：本机 7860 被其它应用占用，产品默认 7861（`M2A_PORT` 可改）；预览端口动态分配。
- 生成的独立 Agent 不依赖 Builder 内存对象，拥有自身 SDK 会话与真实权重。
