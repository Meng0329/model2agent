"""Real Claude Agent SDK session bridge for the main Model2Agent.

This is the ONLY agent runtime. It spawns a Claude Code CLI subprocess pointed at
the Anthropic-compatible DeepSeek endpoint and streams genuine events:
 - StreamEvent text_delta            -> incremental assistant text
 - StreamEvent content_block_start   -> a real tool/exec card begins (running)
 - AssistantMessage ToolResultBlock  -> the card's real result (done/error)
No self-written agent loop, no OpenAI fallback, no fabricated tool calls.
"""
from __future__ import annotations
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    StreamEvent, AssistantMessage, ToolUseBlock, ToolResultBlock,
    ResultMessage, SystemMessage, TextBlock, UserMessage,
)

from . import config


@dataclass
class ToolCard:
    id: str
    name: str
    status: str = "running"        # running -> done | error
    input: str = ""
    result: str = ""
    started_at: float = 0.0


class AgentSession:
    """One continuous Claude Agent SDK session bound to one task/workspace."""

    def __init__(self, cwd: str | Path, allowed_tools=None, first_prompt: str | None = None):
        self.cwd = str(cwd)
        self.allowed_tools = allowed_tools or config.MAIN_TOOLS
        self.first_prompt = first_prompt
        self.client: ClaudeSDKClient | None = None
        self.session_id = uuid.uuid4().hex[:16]
        self._cards: dict[str, ToolCard] = {}
        self.connected = False

    async def connect(self) -> None:
        if self.connected:
            return
        opts = ClaudeAgentOptions(
            model=config.DEEPSEEK_MODEL,
            cwd=self.cwd,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            allowed_tools=self.allowed_tools,
            # Only load the *project* skill/config, never the user's global
            # ~/.claude/CLAUDE.md — keeps the product's output clean and isolated.
            setting_sources=["project"],
            env=config.agent_env(),
        )
        self.client = ClaudeSDKClient(options=opts)
        # Only pass a real first prompt; connect() with an empty string sends a
        # blank user message the model treats as "empty input".
        await self.client.connect(self.first_prompt if self.first_prompt else None)
        self.connected = True

    def _ev(self, kind: str, **kw) -> dict:
        return {"type": kind, **kw}

    async def respond(self, prompt: str):
        """Async generator of real events for one user turn.

        Yields {"type":"text","text":...} for incremental deltas,
                {"type":"tool",...} for tool-card lifecycle,
                {"type":"result", "text":..., "is_error":...} once at the end.
        """
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
                # Built-in tools return their result as a UserMessage with a
                # ToolResultBlock. Mark the matching card done with real output.
                content = m.content if isinstance(m.content, list) else []
                for b in content:
                    if isinstance(b, ToolResultBlock):
                        res = str(b.content)[:2000]
                        cid = b.tool_use_id
                        card = self._cards.get(cid) if cid in self._cards else None
                        if card is None:
                            # attach to the latest running card
                            running = [c for c in self._cards.values() if c.status == "running"]
                            card = running[-1] if running else None
                        if card is not None:
                            card.status = "done"
                            card.result = res
                            yield self._ev("tool", card_id=card.id, name=card.name,
                                           status="done", input=card.input, result=res)
            elif isinstance(m, ResultMessage):
                yield self._ev("result", text="".join(stream_parts), is_error=bool(m.is_error),
                               stop_reason=m.stop_reason, cost=m.total_cost_usd)
                return

    def _last_running_id(self) -> str | None:
        for cid, c in list(self._cards.items())[::-1]:
            return cid
        return None

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

    async def get_or_create(self, task_id: str, cwd, first_prompt: str | None = None) -> AgentSession:
        async with self._lock:
            if task_id in self._sessions:
                return self._sessions[task_id]
            s = AgentSession(cwd=cwd, first_prompt=first_prompt)
            self._sessions[task_id] = s
            return s

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
