"""Unified LLM runtime for Model2Agent.

The fixed stack requires the **Claude Agent SDK** to be wired in. We use it as the
orchestration/runtime layer: when a Claude Agent SDK client can be constructed (i.e. an
API key / base URL is reachable), route prompts through it; otherwise fall back to the
OpenAI-compatible DeepSeek client (also declared in the fixed stack). Model2Agent never
hard-codes keys; secrets come from the environment only.

This module is the single place that decides which transport to use, so the rest of the
pipeline stays agnostic.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from . import config
from .llm import LLMClient, unwrap_result, scrub


def _sdk_available() -> bool:
    try:
        import claude_agent_sdk  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class RuntimeResult:
    text: str
    ok: bool
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    raw: str = ""
    error: Optional[str] = None
    transport: str = "unknown"
    records: list = field(default_factory=list)


class Runtime:
    """Routes prompts to Claude Agent SDK (preferred) or DeepSeek OpenAI client (fallback)."""

    def __init__(self, method_tag: str = "runtime", prefer_sdk: bool = True):
        self.method_tag = method_tag
        self.prefer_sdk = prefer_sdk and _sdk_available()
        self._openai = LLMClient(method_tag)
        self._sdk_client = None
        if self.prefer_sdk:
            try:
                from claude_agent_sdk import ClaudeAgentOptions
                # Point the SDK at the OpenAI-compatible DeepSeek endpoint as the model base.
                self._sdk_options = ClaudeAgentOptions(
                    model=config.DEEPSEEK_MODEL,
                    max_tokens=2000,
                    base_url=config.DEEPSEEK_BASE_URL,
                    api_key=config.DEEPSEEK_API_KEY,
                )
                self.transport = "claude_sdk"
            except Exception as e:
                self.prefer_sdk = False
                self.transport = "openai_deepseek"
        else:
            self.transport = "openai_deepseek"

    def complete(self, messages: list[dict], *, temperature: float = 0.0,
                 max_tokens: int = 1600, json_mode: bool = False) -> RuntimeResult:
        if self.prefer_sdk:
            try:
                return self._complete_sdk(messages, temperature, max_tokens, json_mode)
            except Exception as e:
                # do not silently succeed; fall back and record
                res = self._complete_openai(messages, temperature, max_tokens, json_mode)
                res.error = f"sdk_fallback: {type(e).__name__}: {e}"
                return res
        return self._complete_openai(messages, temperature, max_tokens, json_mode)

    def _complete_openai(self, messages, temperature, max_tokens, json_mode):
        raw = self._openai.chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
        return RuntimeResult(text=raw, ok=bool(raw), raw=raw, transport="openai_deepseek",
                             records=list(self._openai.records))

    def _complete_sdk(self, messages, temperature, max_tokens, json_mode):
        from claude_agent_sdk import query
        prompt = messages[-1]["content"] if messages else ""
        sys_p = next((m["content"] for m in messages if m["role"] == "system"), "")
        out_parts = []
        import time
        t0 = time.perf_counter()
        for msg in query(prompt=prompt, options=self._sdk_options):
            for block in getattr(msg, "content", []) or []:
                if getattr(block, "text", None):
                    out_parts.append(block.text)
        text = "".join(out_parts)
        if json_mode:
            from .llm import extract_json
            j = extract_json(text)
            text = json.dumps(j, ensure_ascii=False) if j is not None else text
        return RuntimeResult(text=text, ok=bool(text), raw=text, transport="claude_sdk",
                             latency_ms=(time.perf_counter() - t0) * 1000)
