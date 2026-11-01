"""Model2Agent V0.3 — configuration and paths.

Secrets are NEVER hard-coded: they come exclusively from environment variables
(loaded from a gitignored local `.env`). JSONL/CSV logs must never contain keys.
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
if load_dotenv and (ROOT / ".env").exists():
    load_dotenv(ROOT / ".env")

# --- GPU policy: use GPU0 ONLY. Must be set before torch is imported. ---
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# --- LLM (orchestrator / AGCI / baselines all use this OpenAI-compatible endpoint) ---
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.inferaiapi.com/v1")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

# Optional internal high-concurrency endpoint (qwen / reranker / embedding / mineru)
INTERNAL_BASE_URL = os.getenv("INTERNAL_BASE_URL", "http://10.200.37.71:8801/v1")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

# --- Claude Agent SDK runtime (single session, multi-agent) ---
# The SDK subprocess reads ANTHROPIC_*; map them from the DeepSeek credentials once,
# here, so the research runner and the product backend share one mapping.
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "") or DEEPSEEK_BASE_URL.replace("/v1", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "") or DEEPSEEK_API_KEY
CLAUDE_CODE_ALLOW_OTHER_MODELS = "1"

# --- Paths ---
MODEL_ASSETS_DIR = ROOT / "model_assets"
GENERATED_AGENTS_DIR = ROOT / "generated_agents"
RESULTS_DIR = ROOT / "results"
LOGS_DIR = RESULTS_DIR / "logs"
CSV_DIR = RESULTS_DIR / "csv"
FROZEN_DIR = RESULTS_DIR / "frozen"
REPORTS_DIR = RESULTS_DIR / "reports"

# Research runtime data (gitignored): hidden oracles + generated scientist projects.
RESEARCH_DATA_DIR = ROOT / "m2a_data" / "research"
HIDDEN_ORACLE_DIR = RESEARCH_DATA_DIR / "hidden"
SCIENTIST_PROJECTS_DIR = RESEARCH_DATA_DIR / "scientists"

SCIENTIST_TASKS_PATH = FROZEN_DIR / "scientist_tasks.json"
SCIENTIST_RUN_LOG = LOGS_DIR / "scientist_runs.jsonl"
SCIENTIST_SUMMARY_CSV = CSV_DIR / "scientist_summary.csv"

for _d in (GENERATED_AGENTS_DIR, LOGS_DIR, CSV_DIR, FROZEN_DIR, REPORTS_DIR,
           RESEARCH_DATA_DIR, HIDDEN_ORACLE_DIR, SCIENTIST_PROJECTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Experiment constants (aligned to Paper2Agent structure; see docs/paper2agent_alignment.md) ---
REPS_PER_TASK = 5
RANDOM_SEED = 20261029

# --- Scientist-run budgets (enforced, never silently exceeded) ---
SCIENTIST_MAX_TURNS = int(os.getenv("SCIENTIST_MAX_TURNS", "60"))
SCIENTIST_MAX_BUDGET_USD = float(os.getenv("SCIENTIST_MAX_BUDGET_USD", "2.0"))
SCIENTIST_WALL_TIME_S = int(os.getenv("SCIENTIST_WALL_TIME_S", "1800"))
SCIENTIST_ORACLE_BUDGET = int(os.getenv("SCIENTIST_ORACLE_BUDGET", "32"))


def agent_env() -> dict:
    """Environment for the Claude Code CLI subprocess spawned by the SDK."""
    return {
        "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "CLAUDE_CODE_ALLOW_OTHER_MODELS": CLAUDE_CODE_ALLOW_OTHER_MODELS,
        "CUDA_VISIBLE_DEVICES": "0",
    }

# Cost estimate for the orchestrator LLM (USD per 1M tokens) — used for cost accounting.
# deepseek-v4.1-flash pricing placeholder; override via env for real accounting.
LLM_USD_PER_M_INPUT = float(os.getenv("LLM_USD_PER_M_INPUT", "0.15"))
LLM_USD_PER_M_OUTPUT = float(os.getenv("LLM_USD_PER_M_OUTPUT", "0.60"))


def assert_secrets() -> None:
    """Fail fast with a clear message if the runtime LLM key is missing."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env and fill in the key. "
            "Secrets must never be committed to git."
        )
