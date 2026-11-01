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

# System prompt per the Google prompt-engineering whitepaper: ROLE + CONTEXT +
# positive INSTRUCTIONS + explicit OUTPUT FORMAT + one concrete example, with
# variables filled from config.json so it adapts to each asset.
_SYSTEM = (
    f"你是「{CFG['slug']}」这个已训练模型的专属 Agent。\n"
    f"你的世界只有本模型资产与它的真实推理能力：框架={CFG.get('framework','?')}，"
    f"输入类型={CFG.get('input_type','?')}，类别标签={json.dumps(CFG.get('labels', []), ensure_ascii=False)}，"
    f"能力={json.dumps(CFG['capabilities'], ensure_ascii=False)}。\n"
    "边界：不要引用、猜测或泄露任何本模型资产之外的仓库/平台/内部文档知识；"
    "只依据真实推理结果与用户提供的数据回答。\n"
    "工作方式：1) 凡涉及预测/概率/重要性/类别的问题，先调用 run_model 做真实推理，再基于真实返回值回答；"
    "2) 用真实数值说明（预测值、概率百分比、排名），不要编造；"
    "3) 用用户提问的语言回答，结论先行、简洁解释；"
    "4) 用户尚未提供数据而问题需要输入时，明确说明需要什么输入。\n"
    "输出格式：Markdown；结论用 1–2 句话开头，随后用短列表给出真实数值；"
    "不要输出装饰性分隔线或空泛的「等等」。\n"
    "示例——用户问「这是什么数字？」：调用 run_model(capability='predict')，"
    "若返回 9，则回答「这是数字 9。」并给出置信度。"
)

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
            system_prompt=_SYSTEM,
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
        cap_by_id: dict[str, str] = {}
        name_by_id: dict[str, str] = {}

        def _announce(cid, name, inp):
            if cid in announced:
                return None
            announced.add(cid)
            return {"type": "tool", "card_id": cid, "name": name, "status": "running", "input": inp}

        def _text_of(content) -> str:
            if isinstance(content, list):
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        return blk.get("text", "")
            return str(content)

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
                        name_by_id[cid] = name
                        inp = cb.get("input", "")
                        if "run_model" in name and isinstance(inp, dict):
                            cap_by_id[cid] = inp.get("capability", "")
                        e = _announce(cid, name, str(inp)[:400])
                        if e:
                            yield e
            elif isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock):
                        cid = b.id or uuid.uuid4().hex[:8]
                        name_by_id[cid] = b.name
                        if "run_model" in b.name and isinstance(b.input, dict):
                            cap_by_id[cid] = b.input.get("capability", "")
                        e = _announce(cid, b.name, str(b.input)[:400])
                        if e:
                            yield e
            elif isinstance(m, UserMessage):
                for b in (m.content if isinstance(m.content, list) else []):
                    if isinstance(b, ToolResultBlock):
                        name = name_by_id.get(b.tool_use_id, "run_model")
                        yield {"type": "tool", "card_id": b.tool_use_id,
                               "name": name, "status": "error" if b.is_error else "done",
                               "result": str(b.content)[:2000]}
                        if "run_model" in name and not b.is_error:
                            try:
                                parsed = json.loads(_text_of(b.content))
                            except Exception:
                                parsed = None
                            if parsed is not None:
                                att = ATTACHMENTS.get(self.sid) or {}
                                yield {"type": "model_run",
                                       "capability": cap_by_id.get(b.tool_use_id) or CFG.get("default_capability"),
                                       "result": parsed, "trace": att.get("trace")}
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
