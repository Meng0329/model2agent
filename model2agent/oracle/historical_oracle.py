"""Historical real-measurement replay oracle.

The hidden store lives OUTSIDE any agent workspace (mode 0700). Measurements are
real and traceable (ProteinGym DMS fitness, Matbench DFT labels). Every query is
budget-accounted and logged. A candidate with no recorded measurement returns
UNOBSERVABLE — never a proxy, never a simulation.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from ..scientist.budget import Budget, BudgetExceeded

UNOBSERVABLE = "__UNOBSERVABLE__"


class HistoricalOracle:
    """Read-only replay of pre-frozen real measurements, with budget + access log."""

    def __init__(self, hidden_dir: str | Path, *, measurement_file: str,
                 access_log: str | Path, budget: Budget, run_id: str):
        self.hidden_dir = Path(hidden_dir)
        self.measurement_file = measurement_file
        self.access_log = Path(access_log)
        self.budget = budget
        self.run_id = run_id
        if not self.hidden_dir.is_dir():
            raise FileNotFoundError(f"hidden oracle store missing: {self.hidden_dir}")
        if self.hidden_dir.stat().st_mode & 0o077:
            raise PermissionError(
                f"hidden oracle store must be mode 0700, got {oct(self.hidden_dir.stat().st_mode)}")

    def _load(self, key: str) -> dict:
        # key is validated as a bare filename — no path traversal out of hidden_dir.
        if not key or "/" in key or "\\" in key or key in (".", "..") or key.startswith("."):
            raise ValueError(f"invalid oracle key: {key!r}")
        p = self.hidden_dir / key
        if not p.exists():
            raise FileNotFoundError(f"no measurement file for {key!r}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def measure(self, candidate_id: str) -> tuple[Any, str]:
        """Return (measurement, source). Raises BudgetExceeded if over budget."""
        self.budget.tick_experiment()  # every oracle query costs one experiment slot
        self._log(candidate_id)
        data = self._load(self.measurement_file)
        if candidate_id in data:
            return data[candidate_id], "E3"
        return UNOBSERVABLE, "E3"

    def _log(self, candidate_id: str) -> None:
        with open(self.access_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "run_id": self.run_id, "candidate_id": candidate_id,
                "query_ordinal": self.budget.experiments, "ts": time.time(),
            }, ensure_ascii=False) + "\n")
