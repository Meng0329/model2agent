"""Real Claude Agent SDK session bridge for the main Model2Agent.

This is the ONLY agent runtime. It spawns a Claude Code CLI subprocess pointed at
the Anthropic-compatible DeepSeek endpoint and streams genuine events:
 - StreamEvent text_delta            -> incremental assistant text
 - StreamEvent content_block_start   -> a real tool/exec card begins (running)
 - UserMessage ToolResultBlock       -> the card's real result (done/error)
No self-written agent loop, no OpenAI fallback, no fabricated tool calls.

The Builder Agent also exposes `start_preview` / `stop_preview` MCP tools so the
agent itself (not the UI) drives the preview lifecycle, per spec.
"""
from __future__ import annotations
import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    StreamEvent, AssistantMessage, ToolUseBlock, ToolResultBlock,
    ResultMessage, SystemMessage, TextBlock, UserMessage,
    tool, create_sdk_mcp_server,
)

from . import config


# Builder instructions APPENDED to Claude Code's preset system prompt (keeps the
# CLI's tool-use guidance intact). Structured per the Google prompt-engineering
# whitepaper: ROLE + CONTEXT + positive INSTRUCTIONS + OUTPUT FORMAT.
_BUILDER_APPEND = """你是 Model2Agent 的 Builder 智能体：把用户上传的已训练模型资产，变成可独立运行的 Model Agent。

工作区上下文：
- inputs/：模型资产（manifest.json、infer.py、权重、examples.json、metrics.json）。
- project/：你将生成的独立 Agent 项目（React UI + FastAPI + 真实权重 + Dockerfile）。
- 可用技能：agent-generation、agent-testing、model-inspection、model-execution、docker-packaging、react-ui-generation。

工作方式（按顺序）：
1. 读取并理解资产（manifest/infer/examples），确认真实能力与输入类型。
2. 使用 agent-generation 技能，调用 MCP 工具 generate_agent（参数 task_id、asset_dir）做确定性生成。
3. 生成后使用 agent-testing 技能，调用 MCP 工具 verify_agent 做真实推理验证。
4. 需要预览时，调用 start_preview 启动真实进程。
5. 用中文向用户汇报：结论先行，列出真实证据（生成的项目、config、实测预测值）。

输出格式：简洁的 Markdown；每一步给出真实结果；验证失败时如实报告错误原文，绝不把未验证的运行标记为成功。"""


@dataclass
class ToolCard:
    id: str
    name: str
    status: str = "running"        # running -> done | error
    input: str = ""
    result: str = ""
    started_at: float = 0.0


def _make_builder_tools():
    """MCP tools that let the Builder Agent drive generation + preview lifecycle."""
    from .preview import PREVIEWS
    from .workspace import Workspace
    from . import db

    @tool("generate_agent",
          "在任务工作区生成可独立运行的 Agent 项目（React+FastAPI+真实权重+config.json），返回项目摘要。确定性程序执行，非 LLM 文本。",
          {"type": "object",
           "properties": {"task_id": {"type": "string"}, "asset_dir": {"type": "string"}},
           "required": ["task_id"]})
    async def generate_agent(args):
        from .generator import generate
        try:
            proj = generate(args["task_id"], args.get("asset_dir") or f"inputs/{args['task_id']}")
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            db.update_task(args["task_id"], has_generated=1, status="ready")
            from .routers import chat as chat_router
            chat_router._publish(args["task_id"], {"type": "workspace_changed"})
            return {"content": [{"type": "text", "text": json.dumps({
                "ok": True, "project": str(proj), "slug": cfg["slug"],
                "input_type": cfg["input_type"], "capabilities": cfg["capabilities"],
                "vector_len": cfg["vector_len"],
            }, ensure_ascii=False)}]}
        except Exception as e:
            db.update_task(args["task_id"], status="error")
            return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}

    @tool("verify_agent",
          "启动生成的 Agent、探活、运行真实权重自检（model_exec.selfcheck），返回真实推理结果。失败必须如实报告。",
          {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]})
    async def verify_agent(args):
        from .gen_cli import cmd_verify
        import types
        try:
            a = types.SimpleNamespace(task_id=args["task_id"])
            rc = cmd_verify(a)
            return {"content": [{"type": "text", "text": "VERIFY_OK" if rc == 0 else f"VERIFY_FAILED rc={rc}"}]}
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
                                 tools=[generate_agent, verify_agent, start_preview, stop_preview])


class AgentSession:
    """One continuous Claude Agent SDK session bound to one task/workspace."""

    def __init__(self, cwd: str | Path, allowed_tools=None,
                 resume_session_id: str | None = None, with_builder_tools: bool = False):
        self.cwd = str(cwd)
        self.allowed_tools = allowed_tools or config.MAIN_TOOLS
        self.resume_session_id = resume_session_id
        self.with_builder_tools = with_builder_tools
        self.client: ClaudeSDKClient | None = None
        self.session_id: str | None = resume_session_id
        self._cards: dict[str, ToolCard] = {}
        self.connected = False

    async def connect(self) -> None:
        if self.connected:
            return
        opts = dict(
            model=config.DEEPSEEK_MODEL,
            cwd=self.cwd,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            allowed_tools=self.allowed_tools,
            setting_sources=["project"],
            env=config.agent_env(),
            system_prompt={"type": "preset", "preset": "claude_code", "append": _BUILDER_APPEND},
        )
        if self.resume_session_id:
            opts["resume"] = self.resume_session_id
        if self.with_builder_tools:
            opts["mcp_servers"] = {"m2a_builder": _make_builder_tools()}
        self.client = ClaudeSDKClient(options=ClaudeAgentOptions(**opts))
        # connect() WITHOUT a prompt: the SDK would send an empty/None prompt as a
        # user message. All messages are delivered exactly once via query() in respond().
        await self.client.connect()
        self.connected = True

    def _ev(self, kind: str, **kw) -> dict:
        return {"type": kind, **kw}

    async def respond(self, prompt: str):
        """Async generator of real events for one user turn (prompt sent exactly once)."""
        await self.connect()
        await self.client.query(prompt)

        stream_parts: list[str] = []
        announced: set[str] = set()

        def _announce(cid, name, inp):
            if cid in announced:
                return None
            announced.add(cid)
            return self._ev("tool", card_id=cid, name=name, status="running", input=inp)

        async for m in self.client.receive_response():
            if isinstance(m, StreamEvent):
                ev = m.event
                et = ev.get("type")
                if et == "content_block_delta":
                    d = ev.get("delta", {})
                    if d.get("type") == "text_delta":
                        txt = d.get("text", "")
                        stream_parts.append(txt)
                        yield self._ev("text", text=txt)
                elif et == "content_block_start":
                    cb = ev.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        cid = cb.get("id") or ev.get("id") or uuid.uuid4().hex[:8]
                        name = cb.get("name", "tool")
                        self._cards[cid] = ToolCard(id=cid, name=name, input=str(cb.get("input", ""))[:400], started_at=time.time())
                        e = _announce(cid, name, self._cards[cid].input)
                        if e:
                            yield e
            elif isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, TextBlock):
                        pass  # full text arrives as deltas; ignore to avoid duplicate render
                    elif isinstance(b, ToolUseBlock):
                        cid = b.id or uuid.uuid4().hex[:8]
                        if cid not in self._cards:
                            self._cards[cid] = ToolCard(cid, b.name, input=str(b.input)[:400], started_at=time.time())
                        e = _announce(cid, b.name, str(b.input)[:400])
                        if e:
                            yield e
            elif isinstance(m, UserMessage):
                content = m.content if isinstance(m.content, list) else []
                for b in content:
                    if isinstance(b, ToolResultBlock):
                        res = str(b.content)[:2000]
                        cid = b.tool_use_id
                        card = self._cards.get(cid) if cid in self._cards else None
                        if card is None:
                            running = [c for c in self._cards.values() if c.status == "running"]
                            card = running[-1] if running else None
                        if card is not None:
                            card.status = "done"
                            card.result = res
                            yield self._ev("tool", card_id=card.id, name=card.name,
                                           status="done", input=card.input, result=res)
            elif isinstance(m, ResultMessage):
                # Capture the SDK's REAL session id for later resume/restore.
                if m.session_id:
                    self.session_id = m.session_id
                yield self._ev("result", text="".join(stream_parts), is_error=bool(m.is_error),
                               stop_reason=m.stop_reason, cost=m.total_cost_usd,
                               session_id=m.session_id, num_turns=m.num_turns)
                return

    async def interrupt(self) -> None:
        if self.client and self.connected:
            await self.client.interrupt()

    async def close(self) -> None:
        if self.client and self.connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.connected = False


class SessionManager:
    """Registry of live sessions keyed by task_id. One session per task."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()

    def has(self, task_id: str) -> bool:
        return task_id in self._sessions and self._sessions[task_id].connected

    async def get_or_create(self, task_id: str, cwd, resume_session_id: str | None = None,
                            with_builder_tools: bool = False) -> AgentSession:
        async with self._lock:
            if task_id in self._sessions:
                return self._sessions[task_id]
            s = AgentSession(cwd=cwd, resume_session_id=resume_session_id,
                             with_builder_tools=with_builder_tools)
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
