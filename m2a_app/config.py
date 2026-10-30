"""Model2Agent V1.0 product configuration (env-driven, no hard-coded secrets)."""
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
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "m2a_data"           # product-local data (settings, tasks, workspaces)
WORKSPACES_DIR = DATA_DIR / "workspaces"
SKILLS_DIR = APP_DIR / "skills"

# Agent runtime LLM: Claude Agent SDK drives Claude Code CLI, which talks to the
# Anthropic-compatible DeepSeek endpoint. Model name is the *backend* model id the
# gateway accepts; CLAUDE_CODE_ALLOW_OTHER_MODELS lets the CLI pass it through.
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "") or os.getenv("DEEPSEEK_BASE_URL", "").replace("/v1", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

# Tools the main Model2Agent can use inside the workspace.
MAIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)


def agent_env() -> dict:
    """Environment for the Claude Code CLI subprocess spawned by the SDK.

    Crucial settings:
      - ANTHROPIC_BASE_URL : Anthropic-compatible DeepSeek endpoint (CLI appends /v1/messages)
      - ANTHROPIC_API_KEY  : DeepSeek API key
      - CLAUDE_CODE_ALLOW_OTHER_MODELS=1 : let the CLI use the gateway's model id
    """
    return {
        "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "CLAUDE_CODE_ALLOW_OTHER_MODELS": "1",
    }
