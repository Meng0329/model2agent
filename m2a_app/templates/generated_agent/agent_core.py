"""Own Claude Agent SDK session for the generated Model Agent.

This is the generated agent's OWN runtime (independent from the Builder's
in-memory session). It registers a real `run_model` tool backed by model_exec
(real weights) and streams genuine SDK events.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, StreamEvent, AssistantMessage,
    TextBlock, ResultMessage, tool, create_sdk_mcp_server,
)

import model_exec

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

_BASE = (os.getenv("ANTHROPIC_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "").replace("/v1", ""))
_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

_SYSTEM = (
    f"你是 {CFG['slug']} 模型 Agent，可回答关于模型的问题并执行真实推理。\n"
    f"能力列表：{json.dumps(CFG['capabilities'], ensure_ascii=False)}\n"
    f"用 run_model 工具执行推理（capability + args）。只依据真实执行结果回答，不得虚构。"
)


@tool("run_model", "执行模型真实推理，返回 JSON 结果",
      {"type": "object", "properties": {"capability": {"type": "string"}, "args": {"type": "object", "description": "input args matching the capability schema, e.g. {\"features\": [..]}"}}, "required": ["capability"]})
async def run_model(args):
    try:
        cap = args.get("capability")
        a = args.get("args", {})
        out = model_exec.run(cap, a)
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, default=str)[:6000]}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}]}


_server = create_sdk_mcp_server("m2a_model", tools=[run_model])


class GeneratedAgentSession:
    def __init__(self):
        self.client: ClaudeSDKClient | None = None
        self.connected = False

    async def connect(self):
        if self.connected:
            return
        opts = ClaudeAgentOptions(
            model=_MODEL, cwd=str(HERE), permission_mode="bypassPermissions",
            include_partial_messages=True, system_prompt=_SYSTEM,
            allowed_tools=["mcp__m2a_model__run_model", "run_model", "Skill"],
            mcp_servers={"m2a_model": _server},
            setting_sources=["project"],
            env={"ANTHROPIC_BASE_URL": _BASE, "ANTHROPIC_API_KEY": _KEY,
                 "CLAUDE_CODE_ALLOW_OTHER_MODELS": "1"},
        )
        self.client = ClaudeSDKClient(options=opts)
        await self.client.connect()
        self.connected = True

    async def respond(self, prompt: str):
        await self.connect()
        await self.client.query(prompt)
        parts = []
        async for m in self.client.receive_response():
            if isinstance(m, StreamEvent):
                ev = m.event
                if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                    txt = ev["delta"]["text"]
                    parts.append(txt)
                    yield {"type": "text", "text": txt}
            elif isinstance(m, ResultMessage):
                yield {"type": "result", "text": "".join(parts), "is_error": bool(m.is_error)}
                return

    async def close(self):
        if self.client and self.connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.connected = False
