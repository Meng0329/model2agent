"""Own Claude Agent SDK session for the generated Model Agent.

This is the generated agent's OWN runtime (independent from the Builder's
in-memory session). It registers a real `run_model` tool backed by model_exec
(real weights) and streams genuine SDK events.

Per-browser-session isolation: sessions are keyed by a client session_id
(cookie/tab), so different browser sessions NEVER share one SDK context.
The `run_model` MCP server is built per session so the tool can read that
session's most recent uploaded input (attachment) when args omit features.
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, StreamEvent, AssistantMessage,
    TextBlock, ToolUseBlock, ToolResultBlock, ResultMessage, UserMessage,
    tool, create_sdk_mcp_server,
)

import model_exec

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

_BASE = (os.getenv("ANTHROPIC_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "").replace("/v1", ""))
_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

# sid -> most recent uploaded attachment (set by app.py on /api/upload + /api/chat)
ATTACHMENTS: dict[str, dict] = {}


def _attach_hint(att: dict | None) -> str:
    """Describe the uploaded input to the model so it can reason about it honestly."""
    if not att:
        return ""
    it = att.get("input_type")
    if it == "image":
        return (f"用户已上传一张图片并转换为特征向量（{att.get('vector_len')} 维）。"
                f"如需推理，调用 run_model，args 传 {{'capability': '<能力>', 'args': {{'features': <特征>}}}}。"
                f"若不确定特征值，可省略 features，工具会自动使用当前会话最近上传的输入。")
    if it == "tabular":
        return (f"用户已上传 CSV 数据，共 {len(att.get('rows', []))} 行，已按特征顺序解析。"
                f"调用 run_model 推理，args 传 {{'capability': '<能力>', 'args': {{'features': <某行特征>}}}}。"
                f"可省略 features，工具会自动使用当前会话最近上传的输入。")
    if it == "vector":
        return "用户已提供特征向量。调用 run_model，args 传 {'capability': '<能力>', 'args': {'features': <向量>}}。"
    if it == "text":
        return "用户已提供文本输入。"
    return ""


def _features_from_attachment(sid: str) -> list | None:
    att = ATTACHMENTS.get(sid) or {}
    if att.get("input_type") == "image":
        return att.get("features")
    if att.get("input_type") == "vector":
        return att.get("features")
    if att.get("input_type") == "tabular":
        rows = att.get("rows") or []
        return rows[0].get("features") if rows else None
    return None


class _Session:
    def __init__(self, sid: str):
        self.sid = sid
        self.client: ClaudeSDKClient | None = None
        self.connected = False

    def _make_server(self):
        """Per-session MCP server so run_model can read THIS session's input."""
        sid = self.sid

        @tool("run_model", "执行模型真实推理，返回 JSON 结果",
              {"type": "object",
               "properties": {"capability": {"type": "string"},
                              "args": {"type": "object", "description": "capability 的参数，如 {\"features\": [..]}; 省略 features 时使用当前会话最近上传的输入"}},
               "required": ["capability"]})
        async def run_model(args):
            try:
                cap = args.get("capability") or CFG.get("default_capability") or "predict"
                a = dict(args.get("args") or {})
                if "features" not in a:
                    feats = _features_from_attachment(sid)
                    if feats is not None:
                        a["features"] = feats
                out = model_exec.run(cap, a)
                return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, default=str)[:6000]}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}

        return create_sdk_mcp_server("m2a_model", tools=[run_model])

    async def connect(self):
        if self.connected:
            return
        opts = ClaudeAgentOptions(
            model=_MODEL, cwd=str(HERE), permission_mode="bypassPermissions",
            include_partial_messages=True,
            system_prompt=(
                f"你是 {CFG['slug']} 模型 Agent，可回答关于模型的问题并执行真实推理。\n"
                f"能力列表：{json.dumps(CFG['capabilities'], ensure_ascii=False)}\n"
                f"用 run_model 工具执行推理（capability + args）。只依据真实执行结果回答，不得虚构。"
            ),
            allowed_tools=["mcp__m2a_model__run_model", "run_model", "Skill"],
            mcp_servers={"m2a_model": self._make_server()},
            setting_sources=["project"],
            env={"ANTHROPIC_BASE_URL": _BASE, "ANTHROPIC_API_KEY": _KEY,
                 "CLAUDE_CODE_ALLOW_OTHER_MODELS": "1"},
        )
        self.client = ClaudeSDKClient(options=opts)
        await self.client.connect()
        self.connected = True

    async def respond(self, prompt: str, attachment: dict | None = None):
        await self.connect()
        if attachment:
            ATTACHMENTS[self.sid] = attachment
        if attachment:
            prompt = f"{_attach_hint(attachment)}\n\n{prompt}"
        await self.client.query(prompt)

        parts: list[str] = []
        announced: set[str] = set()

        def _announce(cid, name, inp):
            if cid in announced:
                return None
            announced.add(cid)
            return {"type": "tool", "card_id": cid, "name": name, "status": "running", "input": inp}

        async for m in self.client.receive_response():
            if isinstance(m, StreamEvent):
                ev = m.event
                if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                    txt = ev["delta"]["text"]
                    parts.append(txt)
                    yield {"type": "text", "text": txt}
                elif ev.get("type") == "content_block_start":
                    cb = ev.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        cid = cb.get("id") or ev.get("id") or uuid.uuid4().hex[:8]
                        name = cb.get("name", "tool")
                        e = _announce(cid, name, str(cb.get("input", ""))[:400])
                        if e:
                            yield e
            elif isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock):
                        cid = b.id or uuid.uuid4().hex[:8]
                        e = _announce(cid, b.name, str(b.input)[:400])
                        if e:
                            yield e
            elif isinstance(m, UserMessage):
                for b in (m.content if isinstance(m.content, list) else []):
                    if isinstance(b, ToolResultBlock):
                        yield {"type": "tool", "card_id": b.tool_use_id,
                               "name": "run_model", "status": "error" if b.is_error else "done",
                               "result": str(b.content)[:2000]}
            elif isinstance(m, ResultMessage):
                yield {"type": "result", "text": "".join(parts), "is_error": bool(m.is_error)}
                return

    async def interrupt(self):
        if self.client and self.connected:
            try:
                await self.client.interrupt()
            except Exception:
                pass

    async def close(self):
        if self.client and self.connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.connected = False


class SessionManager:
    """One SDK session per browser session_id. NO global singleton."""

    def __init__(self):
        self._sessions: dict[str, _Session] = {}
        self._lock = asyncio.Lock()

    async def get(self, sid: str) -> _Session:
        async with self._lock:
            if sid not in self._sessions:
                self._sessions[sid] = _Session(sid)
            return self._sessions[sid]

    async def close(self, sid: str) -> None:
        async with self._lock:
            s = self._sessions.pop(sid, None)
        if s:
            await s.close()

    async def close_all(self) -> None:
        for sid in list(self._sessions):
            await self.close(sid)


SESSIONS = SessionManager()
