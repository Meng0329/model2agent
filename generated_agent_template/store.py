"""Conversation store for the generated Model Agent (project-scoped, JSON file).

Persists conversations to <project>/conversations.json with atomic writes. This is
the generated agent's OWN state, deliberately kept inside the generated project and
never touching the Builder's database. No external DB dependency.
"""
from __future__ import annotations
import json
import os
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
_STORE = HERE / "conversations.json"
_LOCK = threading.Lock()


def _now() -> float:
    return time.time()


def _load() -> dict:
    if not _STORE.exists():
        return {"version": 1, "conversations": []}
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "conversations": []}


def _save(data: dict) -> None:
    tmp = _STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, _STORE)


def _find(data: dict, cid: str) -> dict | None:
    for c in data["conversations"]:
        if c["id"] == cid:
            return c
    return None


def list_conversations() -> list[dict]:
    with _LOCK:
        data = _load()
        out = []
        for c in data["conversations"]:
            out.append({
                "id": c["id"],
                "title": c.get("title") or "新会话",
                "created_at": c.get("created_at"),
                "updated_at": c.get("updated_at"),
                "message_count": len(c.get("messages", [])),
                "last_preview": (c.get("messages") or [{}])[-1].get("content", "")[:80] if c.get("messages") else "",
            })
        out.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
        return out


def create_conversation(title: str | None = None) -> dict:
    with _LOCK:
        data = _load()
        cid = uuid.uuid4().hex
        conv = {"id": cid, "title": title or "新会话", "created_at": _now(),
                "updated_at": _now(), "messages": []}
        data["conversations"].append(conv)
        _save(data)
        return conv


def ensure_conversation(cid: str, title: str | None = None) -> dict:
    """Create the conversation with the caller-provided id if it does not exist."""
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        if c is not None:
            return c
        conv = {"id": cid, "title": title or "新会话", "created_at": _now(),
                "updated_at": _now(), "messages": []}
        data["conversations"].append(conv)
        _save(data)
        return conv


def rename_conversation(cid: str, title: str) -> bool:
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        if c is None:
            return False
        c["title"] = title
        c["updated_at"] = _now()
        _save(data)
        return True


def get_messages(cid: str) -> list[dict]:
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        return list(c.get("messages", [])) if c else []


def append_message(cid: str, role: str, content: str, *, cards: list | None = None,
                   attachment: dict | None = None, capability: str | None = None) -> dict:
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        if c is None:
            raise KeyError(f"conversation not found: {cid}")
        msg = {"id": uuid.uuid4().hex, "role": role, "content": content,
               "cards": cards or [], "attachment": attachment, "capability": capability,
               "created_at": _now()}
        c["messages"].append(msg)
        c["updated_at"] = _now()
        _save(data)
        return msg


def update_message(cid: str, mid: str, **kw) -> dict | None:
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        if c is None:
            return None
        for m in c.get("messages", []):
            if m["id"] == mid:
                m.update(kw)
                c["updated_at"] = _now()
                _save(data)
                return m
        return None


def delete_conversation(cid: str) -> bool:
    with _LOCK:
        data = _load()
        before = len(data["conversations"])
        data["conversations"] = [c for c in data["conversations"] if c["id"] != cid]
        if len(data["conversations"]) != before:
            _save(data)
            return True
        return False


def clear_conversation(cid: str) -> bool:
    with _LOCK:
        data = _load()
        c = _find(data, cid)
        if c is None:
            return False
        c["messages"] = []
        c["updated_at"] = _now()
        _save(data)
        return True
