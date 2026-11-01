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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .. import config


@dataclass
class ToolEvent:
    name: str
    input: dict
    status: str                      # running | done | error
    result: Optional[str] = None
    is_error: bool = False


@dataclass
class SessionResult:
    text: str = ""
    is_error: bool = False
    stop_reason: str = ""
    num_turns: int = 0
    session_id: str = ""
    cost_usd: float = 0.0
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
                  max_budget_usd: float | None = None) -> Any:
    """Construct ClaudeAgentOptions. Env is the single source of LLM credentials."""
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        cwd=str(cwd),
        model=config.DEEPSEEK_MODEL,
        permission_mode="bypassPermissions",
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task", "Skill"],
        system_prompt=system_prompt,
        agents=agents,
        mcp_servers=mcp_servers or {},
        setting_sources=["project"],
        env=config.agent_env(),
        max_turns=max_turns or config.SCIENTIST_MAX_TURNS,
        max_budget_usd=max_budget_usd if max_budget_usd is not None else config.SCIENTIST_MAX_BUDGET_USD,
        include_partial_messages=True,
        forward_subagent_text=True,
    )


async def run_session(prompt: str, options: Any,
                      on_text: Callable[[str], None] | None = None) -> SessionResult:
    """Run one SDK session to completion and capture a traceable result."""
    from claude_agent_sdk import ClaudeSDKClient, StreamEvent, AssistantMessage, UserMessage, ResultMessage

    res = SessionResult()
    t0 = time.perf_counter()
    client = ClaudeSDKClient(options)
    await client.connect()
    try:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, StreamEvent):
                if message.type == "content_block_delta" and message.delta and message.delta.type == "text_delta":
                    res.text += message.delta.text
                    if on_text:
                        on_text(message.delta.text)
                elif message.type == "content_block_start" and getattr(message, "content_block", None):
                    cb = message.content_block
                    if cb.type == "tool_use":
                        res.tool_events.append(ToolEvent(cb.name, dict(cb.input or {}), "running"))
            elif isinstance(message, AssistantMessage):
                for block in message.content or []:
                    t = getattr(block, "type", None)
                    if t == "thinking" and getattr(block, "thinking", None):
                        res.thinking.append(block.thinking)
                    elif t == "tool_use":
                        res.tool_events.append(ToolEvent(block.name, dict(block.input or {}), "running"))
                    elif t == "text":
                        res.text += getattr(block, "text", "")
            elif isinstance(message, UserMessage):
                for block in message.content or []:
                    if getattr(block, "type", None) == "tool_result":
                        ev = _last_running(res, getattr(block, "tool_use_id", None))
                        if ev:
                            ev.status = "error" if getattr(block, "is_error", False) else "done"
                            ev.is_error = bool(getattr(block, "is_error", False))
                            try:
                                ev.result = json.dumps(getattr(block, "content", ""), ensure_ascii=False)[:2000]
                            except Exception:
                                ev.result = str(getattr(block, "content", ""))[:2000]
            elif isinstance(message, ResultMessage):
                res.is_error = bool(getattr(message, "is_error", False))
                res.stop_reason = getattr(message, "stop_reason", "")
                res.num_turns = int(getattr(message, "num_turns", 0) or 0)
                res.session_id = getattr(message, "session_id", "") or ""
                res.cost_usd = float(getattr(message, "cost_usd", 0.0) or 0.0)
                if getattr(message, "result", None):
                    res.text = res.text or str(message.result)
    finally:
        await client.disconnect()
    res.latency_ms = (time.perf_counter() - t0) * 1000
    return res


def _last_running(res: SessionResult, tool_use_id: str | None) -> ToolEvent | None:
    if tool_use_id:
        return None  # SDK tool-result blocks don't always carry tool_use_id; fall back to last
    for ev in reversed(res.tool_events):
        if ev.status == "running":
            return ev
    return None
