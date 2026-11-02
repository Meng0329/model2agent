"""Single-session multi-agent runtime for the Model2Agent outer agent.

One Claude Agent SDK session owns the whole conversion. Subagents (registered via
``ClaudeAgentOptions(agents=...)``) are invoked by the main agent through the Agent
tool — there is NO fixed pipeline, NO stage map, NO keyword routing. The agent
decides what to delegate, when, and how to combine the results.

All costs/tokens/latency are captured from the SDK result, never fabricated.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from .. import config


@dataclass
class ToolEvent:
    name: str
    input: dict
    status: str                      # running | done | error
    result: Optional[str] = None
    is_error: bool = False
    id: str = ""


@dataclass
class SessionResult:
    text: str = ""
    is_error: bool = False
    stop_reason: str = ""
    num_turns: int = 0
    session_id: str = ""
    cost_usd: float = 0.0
    tokens: int = 0
    tool_events: list[ToolEvent] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def model_call_count(self) -> int:
        """Count tool calls that actually hit the scientific model (oracle-backed)."""
        return sum(1 for t in self.tool_events if t.name in
                   ("run_model", "score_variant", "energy", "relax") and t.status == "done")


def sdk_version() -> str:
    try:
        import claude_agent_sdk
        return getattr(claude_agent_sdk, "__version__", "unknown")
    except ImportError:  # pragma: no cover
        return "NOT_INSTALLED"


def build_options(*, cwd: str | Path, agents: dict, system_prompt: str,
                  mcp_servers: dict | None = None, max_turns: int | None = None,
                  max_budget_usd: float | None = None,
                  env_override: dict | None = None) -> Any:
    """Construct ClaudeAgentOptions. Env is the single source of LLM credentials.

    ``env_override`` lets a non-research caller (e.g. the product) supply its own
    env so the research GPU0 forcing is NOT applied to the product, which must
    respect the user-selected device. Omit it to use the research env (GPU0).
    """
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        cwd=str(cwd),
        model=config.DEEPSEEK_MODEL,
        permission_mode="bypassPermissions",
        tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task"],
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task"],
        system_prompt=system_prompt,
        agents=agents,
        mcp_servers=mcp_servers or {},
        # SDK isolation: do NOT load the repo's .claude settings/hooks/CLAUDE.md.
        # Otherwise harness hooks (task-watch etc.) contaminate the experiment.
        setting_sources=[],
        env=env_override if env_override is not None else config.agent_env(),
        max_turns=max_turns or config.SCIENTIST_MAX_TURNS,
        max_budget_usd=max_budget_usd if max_budget_usd is not None else config.SCIENTIST_MAX_BUDGET_USD,
        include_partial_messages=True,
        forward_subagent_text=True,
    )


async def stream_session(prompt: str, options: Any,
                         holder: dict | None = None) -> AsyncIterator[dict]:
    """Run one SDK session, yielding live events shaped for the product SSE layer.

    Events: {type:text|tool|thinking|result}. If ``holder`` is provided, the live
    ClaudeSDKClient is stored under holder["client"] so the caller can interrupt;
    it is removed on completion. Mirrors run_session's parsing but streams.
    """
    from claude_agent_sdk import (ClaudeSDKClient, StreamEvent, AssistantMessage,
                                  UserMessage, ResultMessage,
                                  ToolUseBlock, ToolResultBlock, ThinkingBlock)

    client = ClaudeSDKClient(options)
    await client.connect()
    if holder is not None:
        holder["client"] = client
    parts: list[str] = []
    announced: set[str] = set()
    name_by_id: dict[str, str] = {}
    running: list[str] = []
    try:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, StreamEvent):
                ev = message.event or {}
                et = ev.get("type")
                if et == "content_block_delta":
                    d = ev.get("delta") or {}
                    if d.get("type") == "text_delta":
                        txt = d.get("text", "") or ""
                        parts.append(txt)
                        yield {"type": "text", "text": txt}
                elif et == "content_block_start":
                    cb = ev.get("content_block") or {}
                    if cb.get("type") == "tool_use":
                        cid = cb.get("id") or ev.get("id") or uuid.uuid4().hex[:8]
                        name = cb.get("name", "tool")
                        name_by_id[cid] = name
                        if cid not in announced:
                            announced.add(cid)
                            running.append(cid)
                            yield {"type": "tool", "card_id": cid, "name": name,
                                   "status": "running",
                                   "input": str(cb.get("input", ""))[:400]}
            elif isinstance(message, AssistantMessage):
                for block in message.content or []:
                    # SDK content blocks are dataclasses with NO ``type`` attr;
                    # isinstance is the only reliable discriminator.
                    if isinstance(block, ThinkingBlock):
                        if block.thinking:
                            yield {"type": "thinking", "text": block.thinking}
                    elif isinstance(block, ToolUseBlock):
                        cid = block.id or uuid.uuid4().hex[:8]
                        name = block.name
                        name_by_id[cid] = name
                        if cid not in announced:
                            announced.add(cid)
                            running.append(cid)
                            yield {"type": "tool", "card_id": cid, "name": name,
                                   "status": "running",
                                   "input": str(block.input)[:400]}
            elif isinstance(message, UserMessage):
                content = message.content if isinstance(message.content, list) else []
                for block in content:
                    if isinstance(block, ToolResultBlock):
                        cid = block.tool_use_id
                        if cid not in name_by_id and running:
                            cid = running[-1]      # robust fallback; ids normally match
                        name = name_by_id.get(cid, "tool")
                        if cid in running:
                            running.remove(cid)
                        yield {"type": "tool", "card_id": cid, "name": name,
                               "status": "error" if block.is_error else "done",
                               "result": str(block.content)[:2000]}
            elif isinstance(message, ResultMessage):
                yield {"type": "result", "text": "".join(parts),
                       "is_error": bool(getattr(message, "is_error", False)),
                       "stop_reason": getattr(message, "stop_reason", ""),
                       "session_id": getattr(message, "session_id", "") or "",
                       "num_turns": int(getattr(message, "num_turns", 0) or 0),
                       "cost_usd": float(getattr(message, "total_cost_usd", 0.0) or 0.0)}
                return
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        if holder is not None:
            holder.pop("client", None)


async def run_session(prompt: str, options: Any,
                      on_text: Callable[[str], None] | None = None) -> SessionResult:
    """Run one SDK session to completion and capture a traceable result."""
    from claude_agent_sdk import (ClaudeSDKClient, StreamEvent, AssistantMessage,
                                  UserMessage, ResultMessage,
                                  ToolUseBlock, ToolResultBlock, ThinkingBlock, TextBlock)

    res = SessionResult()
    t0 = time.perf_counter()
    client = ClaudeSDKClient(options)
    await client.connect()
    try:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, StreamEvent):
                ev = message.event or {}
                et = ev.get("type")
                if et == "content_block_delta":
                    delta = ev.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        txt = delta.get("text", "") or ""
                        res.text += txt
                        if on_text:
                            on_text(txt)
                elif et == "content_block_start":
                    cb = ev.get("content_block") or {}
                    if cb.get("type") == "tool_use":
                        res.tool_events.append(ToolEvent(
                            cb.get("name", ""), dict(cb.get("input") or {}),
                            "running", id=cb.get("id", "")))
            elif isinstance(message, AssistantMessage):
                for block in message.content or []:
                    # SDK blocks are dataclasses without a ``type`` field — use
                    # isinstance, otherwise tool results/thinking are dropped.
                    if isinstance(block, ThinkingBlock):
                        if block.thinking:
                            res.thinking.append(block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        res.tool_events.append(ToolEvent(
                            block.name, dict(block.input or {}), "running",
                            id=getattr(block, "id", "")))
                    elif isinstance(block, TextBlock):
                        txt = getattr(block, "text", "") or ""
                        if txt and not res.text.endswith(txt):
                            res.text += txt
            elif isinstance(message, UserMessage):
                for block in message.content or []:
                    if isinstance(block, ToolResultBlock):
                        ev = _match_tool(res, block.tool_use_id)
                        if ev:
                            ev.status = "error" if block.is_error else "done"
                            ev.is_error = bool(block.is_error)
                            try:
                                ev.result = json.dumps(block.content, ensure_ascii=False)[:2000]
                            except Exception:
                                ev.result = str(block.content)[:2000]
            elif isinstance(message, ResultMessage):
                res.is_error = bool(getattr(message, "is_error", False))
                res.stop_reason = getattr(message, "stop_reason", "")
                res.num_turns = int(getattr(message, "num_turns", 0) or 0)
                res.session_id = getattr(message, "session_id", "") or ""
                res.cost_usd = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
                usage = getattr(message, "usage", None) or {}
                res.tokens = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
                if getattr(message, "result", None):
                    res.text = res.text or str(message.result)
    finally:
        await client.disconnect()
    res.latency_ms = (time.perf_counter() - t0) * 1000
    return res


def _match_tool(res: SessionResult, tool_use_id: str | None) -> ToolEvent | None:
    if tool_use_id:
        for ev in res.tool_events:
            if ev.id == tool_use_id:
                return ev
    for ev in reversed(res.tool_events):
        if ev.status == "running":
            return ev
    return None
