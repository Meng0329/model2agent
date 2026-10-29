"""Unified LLM client + cost/latency accounting.

All LLM calls (orchestrator, AGCI capability induction, baselines B0/B2) route
through one OpenAI-compatible client pointed at the DeepSeek endpoint, so cost and
latency are measured identically across methods (a fairness requirement).

No API keys are ever written to logs.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional

from openai import OpenAI

from . import config


@dataclass
class LLMCallRecord:
    method: str            # which method/pipeline stage made the call
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    ok: bool
    error: Optional[str] = None


class LLMClient:
    def __init__(self, method_tag: str = "unknown"):
        config.assert_secrets()
        self.client = OpenAI(base_url=config.DEEPSEEK_BASE_URL, api_key=config.DEEPSEEK_API_KEY)
        self.model = config.DEEPSEEK_MODEL
        self.method_tag = method_tag
        self.records: list[LLMCallRecord] = []

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = False,
        reasoning_effort: str | None = "none",  # disable hidden reasoning: cheaper/faster/deterministic
    ) -> str:
        kwargs = dict(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        rec = LLMCallRecord(method=self.method_tag, model=self.model,
                            prompt_tokens=0, completion_tokens=0, latency_ms=0.0, cost_usd=0.0, ok=False)
        try:
            resp = self.client.chat.completions.create(**kwargs)
            rec.latency_ms = (time.perf_counter() - t0) * 1000
            usage = getattr(resp, "usage", None)
            if usage:
                rec.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                rec.completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            rec.cost_usd = (
                rec.prompt_tokens / 1_000_000 * config.LLM_USD_PER_M_INPUT
                + rec.completion_tokens / 1_000_000 * config.LLM_USD_PER_M_OUTPUT
            )
            rec.ok = True
            return resp.choices[0].message.content or ""
        except Exception as e:  # record failure, do NOT swallow silently
            rec.latency_ms = (time.perf_counter() - t0) * 1000
            rec.error = f"{type(e).__name__}: {e}"[:500]
            raise
        finally:
            self.records.append(rec)

    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def total_tokens(self) -> int:
        return sum(r.prompt_tokens + r.completion_tokens for r in self.records)

    def dump_records(self, path) -> None:
        with open(path, "a", encoding="utf-8") as f:
            for r in self.records:
                f.write(json.dumps({**asdict(r), "ts": time.time()}, ensure_ascii=False) + "\n")


def scrub(text: str) -> str:
    """Remove any accidental key leakage from a string before logging."""
    import re
    text = re.sub(r"sk-[A-Za-z0-9]{20,}", "sk-***", text)
    text = re.sub(r"lgw-[A-Za-z0-9]{20,}", "lgw-***", text)
    return text


def unwrap_result(got):
    """Unwrap common LLM output wrappers like {"result": 9} -> 9.

    Keeps dicts that carry real structure (e.g. predict_proba maps) intact.
    """
    if isinstance(got, dict) and len(got) == 1:
        k = next(iter(got))
        if k in ("result", "value", "answer", "output", "prediction", "pred", "predicted_class"):
            return got[k]
    return got


def extract_json(text: str):
    """Robustly extract a JSON object from possibly-chatty LLM output.

    The DeepSeek endpoint sometimes ignores response_format=json_object and prepends
    prose and/or a ```json fence. Tries: direct parse -> fenced block -> first{..last}.
    """
    import re
    if not text:
        return None
    t = text.strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j != -1 and j > i:
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            pass
    return None
