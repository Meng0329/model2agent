"""SQLite persistence for Model2Agent V2.0.

Stores product state only (tasks, display messages, settings, run ledger).
The SDK Session (context history) and Workspace (files) are managed separately.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from . import config

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    config.ensure_dirs()
    c = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  goal TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'created',   -- created|running|ready|error|stopped
  session_id TEXT,
  device TEXT,
  asset_slug TEXT,
  workspace_path TEXT,
  has_generated INTEGER NOT NULL DEFAULT 0,
  generated_at TEXT,
  preview_state TEXT NOT NULL DEFAULT 'stopped',  -- stopped|starting|running|error
  preview_url TEXT,
  preview_error TEXT,
  docker_status TEXT NOT NULL DEFAULT 'unverified',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,            -- user | assistant
  content TEXT NOT NULL DEFAULT '',
  tool_cards TEXT NOT NULL DEFAULT '[]',
  seq INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  status TEXT NOT NULL,          -- running|completed|failed|cancelled
  started_at TEXT,
  ended_at TEXT,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id, started_at);
"""


def init() -> None:
    with _lock:
        c = _conn()
        try:
            c.executescript(_SCHEMA)
            c.commit()
        finally:
            c.close()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------- tasks ----------------
def create_task(name: str, goal: str, device: str | None = None, asset_slug: str = "") -> dict:
    tid = new_id()
    now = _now()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO tasks(id,name,goal,status,device,asset_slug,workspace_path,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (tid, name, goal, "created", device, asset_slug, str(config.WORKSPACES_DIR / tid), now, now),
            )
            c.commit()
        finally:
            c.close()
    return get_task(tid)


def get_task(task_id: str) -> dict | None:
    with _lock:
        c = _conn()
        try:
            r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        finally:
            c.close()
    return dict(r) if r else None


def list_tasks() -> list[dict]:
    with _lock:
        c = _conn()
        try:
            rows = c.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
        finally:
            c.close()
    return [dict(r) for r in rows]


def update_task(task_id: str, **fields) -> dict | None:
    if not fields:
        return get_task(task_id)
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        c = _conn()
        try:
            c.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
            c.commit()
        finally:
            c.close()
    return get_task(task_id)


def delete_task(task_id: str) -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("DELETE FROM messages WHERE task_id=?", (task_id,))
            c.execute("DELETE FROM runs WHERE task_id=?", (task_id,))
            c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            c.commit()
        finally:
            c.close()


# ---------------- messages ----------------
def append_message(task_id: str, role: str, content: str, tool_cards: list | None = None, seq: int | None = None) -> dict:
    if seq is None:
        seq = next_seq(task_id)
    mid = new_id()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO messages(id,task_id,role,content,tool_cards,seq,created_at) VALUES(?,?,?,?,?,?,?)",
                (mid, task_id, role, content, json.dumps(tool_cards or [], ensure_ascii=False), seq, _now()),
            )
            c.commit()
        finally:
            c.close()
    return {"id": mid, "task_id": task_id, "role": role, "content": content,
            "tool_cards": tool_cards or [], "seq": seq, "created_at": _now()}


def update_message_content(message_id: str, content: str) -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("UPDATE messages SET content=? WHERE id=?", (content, message_id))
            c.commit()
        finally:
            c.close()


def update_message_cards(message_id: str, tool_cards: list) -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("UPDATE messages SET tool_cards=? WHERE id=?",
                      (json.dumps(tool_cards, ensure_ascii=False), message_id))
            c.commit()
        finally:
            c.close()


def get_messages(task_id: str) -> list[dict]:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT * FROM messages WHERE task_id=? ORDER BY seq ASC", (task_id,)).fetchall()
        finally:
            c.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["tool_cards"] = json.loads(d.get("tool_cards") or "[]")
        except Exception:
            d["tool_cards"] = []
        out.append(d)
    return out


def next_seq(task_id: str) -> int:
    with _lock:
        c = _conn()
        try:
            r = c.execute("SELECT COALESCE(MAX(seq),0)+1 AS s FROM messages WHERE task_id=?", (task_id,)).fetchone()
        finally:
            c.close()
    return int(r["s"])


def delete_messages(task_id: str) -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("DELETE FROM messages WHERE task_id=?", (task_id,))
            c.commit()
        finally:
            c.close()


# ---------------- settings ----------------
def set_setting(key: str, value: str) -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, value))
            c.commit()
        finally:
            c.close()


def get_setting(key: str, default: str = "") -> str:
    with _lock:
        c = _conn()
        try:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        finally:
            c.close()
    return r["value"] if r else default


# ---------------- runs ----------------
def start_run(task_id: str) -> str:
    rid = new_id()
    with _lock:
        c = _conn()
        try:
            c.execute("INSERT INTO runs(id,task_id,status,started_at) VALUES(?,?,?,?)",
                      (rid, task_id, "running", _now()))
            c.commit()
        finally:
            c.close()
    return rid


def finish_run(run_id: str, status: str, error: str = "") -> None:
    with _lock:
        c = _conn()
        try:
            c.execute("UPDATE runs SET status=?, ended_at=?, error=? WHERE id=?",
                      (status, _now(), error, run_id))
            c.commit()
        finally:
            c.close()


def is_running(task_id: str) -> bool:
    with _lock:
        c = _conn()
        try:
            r = c.execute("SELECT id FROM runs WHERE task_id=? AND status='running' ORDER BY started_at DESC LIMIT 1",
                          (task_id,)).fetchone()
        finally:
            c.close()
    return r is not None
