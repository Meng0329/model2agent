"""Outer agent bridge — ONE foundation: the model2sci (scientist) multi-agent session.

The product's outer agent is the Model-to-Scientist single-session multi-agent
compiler (`model2agent.scientist.sdk_session` + `BUILDER_AGENTS`), NOT the old
V2 Builder session. It drives the SAME deterministic product tools
(generate_agent / verify_agent / start_preview) so the produced AI-native chat
product is byte-identical to the previous adapted artifact.

Genuine SDK events only:
 - StreamEvent text_delta            -> incremental assistant text
 - StreamEvent content_block_start   -> a real tool/exec card begins (running)
 - UserMessage ToolResultBlock       -> the card's real result (done/error)
No self-written agent loop, no OpenAI fallback, no fabricated tool calls.
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import tool, create_sdk_mcp_server

from . import config


# Outer external-agent mission: the model2sci (scientist) compiler. It reasons as a
# single session with specialized subagents, but produces the SAME AI-native chat
# product via the deterministic tools (so the artifact and its adaptation are
# unchanged). Structured per the Google prompt-engineering whitepaper.
_BUILDER_MISSION = """你是 Model2Agent 的「模型→科学家」外层智能体：单会话多智能体。你把用户上传的已训练
模型资产，编译成一个可独立运行、可被 API 调用的 AI 原生 Agent 产品（聊天 UI + 真实权重 + 适配层）。

工作区上下文：
- inputs/：模型资产（manifest.json、infer.py、权重、examples.json、metrics.json）。
- project/：要生成的独立 Agent 项目（React 聊天 UI + FastAPI + 真实权重 + Dockerfile）。

可用子代理（按需调用，无固定顺序）：model-profiler、affordance-analyst、
capability-graph-builder、scientist-synthesizer、verification-auditor。
可用 MCP 工具：
- inspect_model：真实加载资产、跑例、取 sha（接地事实）。
- execution_check：独立重跑原模型并与声称输出严格比对。
- generate_agent：确定性生成产物（与旧适配版一致）。
- verify_agent / get_verify_report：真实启动产物并逐项验证。
- rebuild_ui / start_preview / stop_preview：重建前端、启停预览。

工作协议（必须遵守，AI 原生、无兜底）：
1. 用 inspect_model 确认真实能力、输入约定与类别来源；不得凭猜测。
2. 需要时调用子代理做能力/依赖分析；只声明真实可执行的能力。
3. 调用 generate_agent 生成 project/（配置、适配层、聊天 UI 全部由确定性程序产生，
   保证与旧 model2agent 适配版一致；你不要手写 config/adapters/前端）。
4. 生成后必须调用 verify_agent 做真实可用性验证（boot / 真实推理 / 输入适配 fixture /
   输入不变性 / 会话 CRUD / API 文档 / chat）。任何一项失败：读取 evidence，定位并改写
   project/ 实现，调用 rebuild_ui 重建前端，再重验，直到 ok=true。
5. 不得用“猜一个/默认一个/静默回退”让检查通过；无法从资产确证的事实如实报告缺什么。
6. 需要预览时调用 start_preview。
7. 用中文向用户汇报：结论先行，附真实证据（生成项目、config、实测预测值、验证报告）。

输出格式：简洁 Markdown。每个要点一行，数值与状态用真实值；不要装饰性分隔线或星号堆砌。
验证未通过时绝不说成功。每次调用工具前最多一句话说明意图。"""


@dataclass
class ToolCard:
    id: str
    name: str
    status: str = "running"        # running -> done | error
    input: str = ""
    result: str = ""
    started_at: float = 0.0


def _make_builder_tools():
    """MCP tools that let the Builder Agent drive generation + verification + preview."""
    from .preview import PREVIEWS
    from .workspace import Workspace
    from . import db

    @tool("generate_agent",
          "在任务工作区生成可独立运行的 Agent 项目（React+FastAPI+真实权重+config.json+agent_ui.json），返回项目摘要。确定性程序执行，非 LLM 文本。",
          {"type": "object",
           "properties": {"task_id": {"type": "string"}, "asset_dir": {"type": "string"}},
           "required": ["task_id"]})
    async def generate_agent(args):
        from .generator import generate
        try:
            proj = generate(args["task_id"], args.get("asset_dir") or f"inputs/{args['task_id']}")
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            ui = json.loads((proj / "agent_ui.json").read_text(encoding="utf-8"))
            db.update_task(args["task_id"], has_generated=1, status="ready")
            from .routers import chat as chat_router
            chat_router._publish(args["task_id"], {"type": "workspace_changed"})
            return {"content": [{"type": "text", "text": json.dumps({
                "ok": True, "project": str(proj), "slug": cfg["slug"],
                "input_type": cfg["input_type"], "capabilities": cfg["capabilities"],
                "vector_len": cfg["vector_len"], "presets": ui.get("presets", []),
            }, ensure_ascii=False)}]}
        except Exception as e:
            db.update_task(args["task_id"], status="error")
            return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}

    @tool("verify_agent",
          "启动生成的 Agent 并做真实可用性验证，返回逐项证据（boot/真实推理/输入适配 fixture/会话 CRUD/API 文档/chat）。失败时必须依据证据改写后重验。",
          {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]})
    async def verify_agent(args):
        from .gen_cli import build_verify_report
        try:
            report = build_verify_report(args["task_id"])
            return {"content": [{"type": "text", "text": json.dumps(report, ensure_ascii=False, default=str)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}

    @tool("get_verify_report",
          "读取最近一次 verify_agent 保存的完整证据报告（project/.m2a_verify.json）",
          {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]})
    async def get_verify_report(args):
        p = Workspace(args["task_id"]).project / ".m2a_verify.json"
        if not p.exists():
            return {"content": [{"type": "text", "text": "no verification report yet"}]}
        return {"content": [{"type": "text", "text": p.read_text(encoding="utf-8")}]}

    @tool("rebuild_ui",
          "在生成项目的 web/ 下执行 npm install + build，重建 web/dist（改写前端后必须调用）",
          {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]})
    async def rebuild_ui(args):
        import subprocess
        web = Workspace(args["task_id"]).project / "web"
        if not (web / "package.json").exists():
            return {"content": [{"type": "text", "text": "ERROR: project/web/package.json not found"}]}
        try:
            for cmd in (["npm", "install", "--no-audit", "--no-fund"], ["npm", "run", "build"]):
                r = subprocess.run(cmd, cwd=str(web), capture_output=True, text=True, timeout=600)
                if r.returncode != 0:
                    return {"content": [{"type": "text", "text":
                            f"BUILD_FAILED {' '.join(cmd)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"}]}
            return {"content": [{"type": "text", "text": "BUILD_OK"}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}

    @tool("start_preview",
          "启动当前任务的生成项目预览（独立进程，使用任务选定设备），返回运行状态与 URL",
          {"type": "object",
           "properties": {"task_id": {"type": "string"}, "device": {"type": "string"}},
           "required": ["task_id"]})
    async def start_preview(args):
        from . import db
        task_id = args.get("task_id")
        device = args.get("device") or db.get_setting("device", "") or "cuda:0"
        entry = Workspace(task_id).project / "run.py"
        st = PREVIEWS.start(task_id, str(entry), device=device)
        msg = f"preview {st.status}" + (f" at {st.url}" if st.url else "") + (f" err={st.error}" if st.error else "")
        return {"content": [{"type": "text", "text": msg}]}

    @tool("stop_preview",
          "停止当前任务正在运行的预览进程",
          {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]})
    async def stop_preview(args):
        task_id = args.get("task_id")
        from .preview import PREVIEWS
        PREVIEWS.stop(task_id)
        return {"content": [{"type": "text", "text": "preview stopped"}]}

    return create_sdk_mcp_server("m2a_builder",
                                 tools=[generate_agent, verify_agent, get_verify_report,
                                        rebuild_ui, start_preview, stop_preview])


class AgentSession:
    """One continuous model2sci (scientist) session bound to one task/workspace.

    Foundation = the Model-to-Scientist single-session multi-agent compiler
    (`model2agent.scientist`). The AI-native chat product is still produced by
    the deterministic MCP tools, so the artifact and its adaptation are unchanged.
    """

    def __init__(self, cwd: str | Path, allowed_tools=None,
                 resume_session_id: str | None = None, with_builder_tools: bool = False,
                 env_override: dict | None = None):
        self.cwd = str(cwd)
        self.resume_session_id = resume_session_id
        self.with_builder_tools = with_builder_tools
        # Product env (no GPU0 forcing); None would fall back to the research env.
        self.env_override = env_override
        self.session_id: str | None = resume_session_id
        self._holder: dict = {}
        self.connected = False

    def _options(self):
        from model2agent.scientist.sdk_session import build_options
        from model2agent.scientist.subagents import BUILDER_AGENTS
        from model2agent.scientist.tools import make_builder_tools as make_scientist_builder_tools

        mcp: dict = {"m2a_builder_tools": make_scientist_builder_tools()}
        if self.with_builder_tools:
            mcp["m2a_builder"] = _make_builder_tools()
        opts = build_options(
            cwd=self.cwd,
            agents=BUILDER_AGENTS,
            system_prompt=_BUILDER_MISSION,
            mcp_servers=mcp,
            env_override=(self.env_override if self.env_override is not None
                          else config.agent_env()),
        )
        if self.resume_session_id:
            opts.resume = self.resume_session_id
        return opts

    async def respond(self, prompt: str):
        """Async generator of real events for one user turn (prompt sent exactly once)."""
        from model2agent.scientist.sdk_session import stream_session
        self.connected = True
        try:
            async for ev in stream_session(prompt, self._options(), holder=self._holder):
                if ev.get("type") == "result" and ev.get("session_id"):
                    self.session_id = ev["session_id"]
                yield ev
        finally:
            self.connected = False

    async def interrupt(self) -> None:
        client = self._holder.get("client")
        if client is not None:
            try:
                await client.interrupt()
            except Exception:
                pass

    async def close(self) -> None:
        self.connected = False


class SessionManager:
    """Registry of live sessions keyed by task_id. One session per task."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()

    def has(self, task_id: str) -> bool:
        return task_id in self._sessions and self._sessions[task_id].connected

    async def get_or_create(self, task_id: str, cwd, resume_session_id: str | None = None,
                            with_builder_tools: bool = False,
                            env_override: dict | None = None) -> AgentSession:
        async with self._lock:
            if task_id in self._sessions:
                return self._sessions[task_id]
            s = AgentSession(cwd=cwd, resume_session_id=resume_session_id,
                             with_builder_tools=with_builder_tools,
                             env_override=env_override)
            self._sessions[task_id] = s
            return s

    def get(self, task_id: str) -> AgentSession | None:
        return self._sessions.get(task_id)

    async def interrupt(self, task_id: str) -> None:
        if task_id in self._sessions:
            await self._sessions[task_id].interrupt()

    async def close(self, task_id: str) -> None:
        if task_id in self._sessions:
            await self._sessions[task_id].close()
            del self._sessions[task_id]

    async def close_all(self) -> None:
        for tid in list(self._sessions):
            await self.close(tid)


SESSIONS = SessionManager()
