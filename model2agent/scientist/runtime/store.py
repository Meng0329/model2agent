"""Self-contained budget, evidence ledger, and historical-oracle client."""
from __future__ import annotations

import json
import time
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, max_tokens: int, max_model_calls: int, max_experiments: int,
                 max_wall_seconds: float, max_usd: float):
        self.max_tokens = max_tokens
        self.max_model_calls = max_model_calls
        self.max_experiments = max_experiments
        self.max_wall_seconds = max_wall_seconds
        self.max_usd = max_usd
        self.tokens_used = 0
        self.model_calls = 0
        self.experiments = 0
        self.cost_usd = 0.0
        self._t0 = time.perf_counter()

    def tick_model_call(self, tokens: int = 0, cost_usd: float = 0.0) -> None:
        self.model_calls += 1
        self.tokens_used += tokens
        self.cost_usd += cost_usd
        self._check()

    def tick_experiment(self) -> None:
        self.experiments += 1
        self._check()

    def _check(self) -> None:
        if self.model_calls > self.max_model_calls:
            raise BudgetExceeded(f"model calls {self.model_calls}>{self.max_model_calls}")
        if self.experiments > self.max_experiments:
            raise BudgetExceeded(f"experiments {self.experiments}>{self.max_experiments}")
        if self.tokens_used > self.max_tokens:
            raise BudgetExceeded(f"tokens {self.tokens_used}>{self.max_tokens}")
        if self.cost_usd > self.max_usd:
            raise BudgetExceeded(f"cost ${self.cost_usd:.4f}>${self.max_usd}")
        if (time.perf_counter() - self._t0) > self.max_wall_seconds:
            raise BudgetExceeded("wall-clock exceeded")

    def as_dict(self) -> dict:
        return {"model_calls": self.model_calls, "experiments": self.experiments,
                "tokens_used": self.tokens_used, "cost_usd": self.cost_usd,
                "elapsed_s": round(time.perf_counter() - self._t0, 3)}


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> str:
        if record.get("evidence_type") in ("E3", "E4") and not record.get("execution_evidence"):
            raise ValueError("E3/E4 require traceable execution evidence")
        rid = f"ev-{len(self.read_all()) + 1}"
        record = {**record, "id": rid, "ts": time.time()}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return rid

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


UNOBSERVABLE = "__UNOBSERVABLE__"


class HistoricalOracleClient:
    """Budgeted read-only client for real historical measurements."""

    def __init__(self, hidden_dir: str | Path, measurement_file: str,
                 access_log: str | Path, budget: Budget, run_id: str):
        self.hidden_dir = Path(hidden_dir)
        self.measurement_file = measurement_file
        self.access_log = Path(access_log)
        self.budget = budget
        self.run_id = run_id
        if not self.hidden_dir.is_dir():
            raise FileNotFoundError(f"hidden oracle store missing: {self.hidden_dir}")

    def _load(self) -> dict:
        name = self.measurement_file
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"invalid measurement file: {name!r}")
        with open(self.hidden_dir / name, encoding="utf-8") as f:
            return json.load(f)

    def measure(self, candidate_id: str):
        self.budget.tick_experiment()
        with open(self.access_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"run_id": self.run_id, "candidate_id": candidate_id,
                                "ordinal": self.budget.experiments, "ts": time.time()}) + "\n")
        data = self._load()
        return data.get(candidate_id, UNOBSERVABLE)
