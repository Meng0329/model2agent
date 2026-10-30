"""Model2Agent V2.0 backend configuration (env-driven, no hard-coded secrets)."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load project .env (walk up from this file) for API keys / endpoints.
_root = Path(__file__).resolve().parents[1]
for _d in [_root, _root / ".."]:
    _p = _d / ".env"
    if _p.exists():
        load_dotenv(_p)
        break

ROOT = _root
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "m2a_data"                       # product-local data (tasks, workspaces, db)
WORKSPACES_DIR = DATA_DIR / "workspaces"
GENERATED_DIR = ROOT / "generated_agents"          # standalone generated agents
DB_PATH = DATA_DIR / "v2.db"
SKILLS_DIR = BACKEND_DIR / "skills"
# Frontend production build (served by FastAPI in prod); dev uses Vite dev server.
FRONTEND_DIST = ROOT / "frontend" / "dist"
FRONTEND_DEV_URL = os.getenv("FRONTEND_DEV_URL", "http://localhost:5173")

# Agent runtime LLM: Claude Agent SDK drives Claude Code CLI -> Anthropic-compatible DeepSeek.
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "") or os.getenv("DEEPSEEK_BASE_URL", "").replace("/v1", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

# Tools the main Model2Agent Builder can use inside the workspace.
MAIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def agent_env() -> dict:
    """Env for the Claude Code CLI subprocess spawned by the SDK."""
    return {
        "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "CLAUDE_CODE_ALLOW_OTHER_MODELS": "1",
    }
