"""Uniform resource budget enforcement for scientist runs.

Every method (B0-B3, M) is subject to the SAME budget. Exceeding any limit is a
hard, loud failure — never a silent clamp or a fallback to a cheaper path.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised when a run exceeds its pre-registered resource budget."""


@dataclass
class Budget:
    max_tokens: int
    max_model_calls: int
    max_experiments: int
    max_wall_seconds: float
    max_usd: float
    tokens_used: int = 0
    model_calls: int = 0
    experiments: int = 0
    cost_usd: float = 0.0
    _t0: float = field(default_factory=time.perf_counter)

    def tick_model_call(self, tokens: int, cost_usd: float) -> None:
        self.model_calls += 1
        self.tokens_used += tokens
        self.cost_usd += cost_usd
        self._assert()

    def tick_experiment(self) -> None:
        self.experiments += 1
        self._assert()

    def _assert(self) -> None:
        now = time.perf_counter()
        if self.tokens_used > self.max_tokens:
            raise BudgetExceeded(f"token budget exceeded ({self.tokens_used}>{self.max_tokens})")
        if self.model_calls > self.max_model_calls:
            raise BudgetExceeded(f"model-call budget exceeded ({self.model_calls}>{self.max_model_calls})")
        if self.experiments > self.max_experiments:
            raise BudgetExceeded(f"experiment budget exceeded ({self.experiments}>{self.max_experiments})")
        if self.cost_usd > self.max_usd:
            raise BudgetExceeded(f"cost budget exceeded (${self.cost_usd:.4f}>${self.max_usd:.4f})")
        if (now - self._t0) > self.max_wall_seconds:
            raise BudgetExceeded(f"wall-clock budget exceeded ({now - self._t0:.1f}s)")

    def as_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens, "max_model_calls": self.max_model_calls,
            "max_experiments": self.max_experiments, "max_wall_seconds": self.max_wall_seconds,
            "max_usd": self.max_usd, "tokens_used": self.tokens_used,
            "model_calls": self.model_calls, "experiments": self.experiments,
            "cost_usd": self.cost_usd,
            "elapsed_s": round(time.perf_counter() - self._t0, 3),
        }
