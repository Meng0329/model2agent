"""Chat + SSE router: drives the real Builder agent and streams events to the UI.

No agent loop here — agent_bridge owns the SDK session. This router:
  - POST /messages            : start (or enqueue) a run with a user prompt
  - GET  /events (SSE)        : subscribe to the per-task event stream (replay-safe)
  - POST /interrupt           : cancel the active run
  - GET  /messages            : display messages (for restore)
"""
from __future__ import annotations
import asyncio
import json
import uuid
from collections import defaultdict, deque
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import db
from ..agent_bridge import SESSIONS
from ..workspace import Workspace
from ..config import MAIN_TOOLS

router = APIRouter(prefix="/api", tags=["chat"])

# --- in-memory event bus -------------------------------------------------
# task_id -> list of (seq, event_dict). Bounded ring buffer of recent events
# so a reconnect can replay only new events via ?after_seq=.
_EVENTS: dict[str, deque] = defaultdict(lambda: deque(maxlen=2000))
# task_id -> set of asyncio.Queue subscribed to live events
_SUBS: dict[str, set[asyncio.Queue]] = defaultdict(set)
_SEQ: dict[str, int] = defaultdict(int)
_RUN_LOCK: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

MAX_EVENTS_PER_FRAME = 50


def _publish(task_id: str, event: dict) -> None:
    _SEQ[task_id] += 1
    event = {**event, "task_id": task_id, "seq": _SEQ[task_id]}
    _EVENTS[task_id].append(event)
    dead = [q for q in _SUBS[task_id] if q.full()]
    for q in dead:
        _SUBS[task_id].discard(q)
    for q in list(_SUBS[task_id]):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            _SUBS[task_id].discard(q)


async def _subscribe(task_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _SUBS[task_id].add(q)
    return q


# --- run coordinator -----------------------------------------------------
async def _run(task_id: str, prompt: str):
    task = db.get_task(task_id)
    if not task:
        return
    run_id = db.start_run(task_id)
    db.update_task(task_id, status="running")
    _publish(task_id, {"type": "run_started", "run_id": run_id})

    # persistence: a single assistant message accumulates text + tool cards
    msg_id = db.append_message(task_id, "assistant", "")["id"]
    tool_cards: list[dict] = []
    card_index: dict[str, dict] = {}
    full_text = ""

    try:
        # ensure a workspace exists (inside try so any failure is reported & run finished)
        ws = Workspace(task_id).create()
        session = await SESSIONS.get_or_create(task_id, str(ws.root), resume_session_id=task.get("session_id"), with_builder_tools=True)
        async for ev in session.respond(prompt):
            kind = ev.get("type")
            if kind == "text":
                full_text += ev.get("text", "")
                _publish(task_id, {"type": "text_delta", "run_id": run_id, "text": ev["text"], "message_id": msg_id})
            elif kind == "tool":
                cid = ev["card_id"]
                card = card_index.get(cid)
                if card is None:
                    card = {"id": cid, "name": ev["name"], "status": ev["status"], "input": ev.get("input", ""), "result": ""}
                    card_index[cid] = card
                    tool_cards.append(card)
                else:
                    card["status"] = ev["status"]
                    if ev.get("result"):
                        card["result"] = ev["result"]
                _publish(task_id, {
                    "type": ("tool_started" if card["status"] == "running" else
                            ("tool_failed" if card["status"] == "error" else "tool_completed")),
                    "run_id": run_id, "card_id": cid, "name": card["name"],
                    "status": card["status"], "input": card["input"], "result": card.get("result", ""),
                })
            elif kind == "result":
                is_err = bool(ev.get("is_error"))
                if ev.get("session_id"):
                    db.update_task(task_id, session_id=ev["session_id"])
                _publish(task_id, {"type": "run_completed" if not is_err else "run_failed", "run_id": run_id,
                                   "text": ev.get("text", ""), "is_error": is_err,
                                   "session_id": ev.get("session_id"), "num_turns": ev.get("num_turns")})
            elif kind == "workspace_changed" or kind == "workspace":
                _publish(task_id, {"type": "workspace_changed", "run_id": run_id})
        db.update_message_content(msg_id, full_text)
        db.update_message_cards(msg_id, tool_cards)
        db.update_task(task_id, status="ready" if not is_err_global(tool_cards) else "ready")
        db.finish_run(run_id, "completed")
    except asyncio.CancelledError:
        db.finish_run(run_id, "cancelled")
        _publish(task_id, {"type": "run_cancelled", "run_id": run_id})
        db.update_task(task_id, status="stopped")
        raise
    except Exception as e:  # noqa
        db.finish_run(run_id, "failed", str(e)[:500])
        _publish(task_id, {"type": "run_failed", "run_id": run_id, "text": "", "error": str(e)[:500]})
        db.update_task(task_id, status="error")
    finally:
        await SESSIONS.close(task_id)
        # detect generation outcome from the filesystem (works whether the agent
        # used the generate_agent MCP tool or ran gen_cli via Bash)
        try:
            cfg = Workspace(task_id).project / "config.json"
            if cfg.exists():
                db.update_task(task_id, has_generated=1, status="ready")
        except Exception:
            pass


def is_err_global(cards: list[dict]) -> bool:
    return any(c.get("status") == "error" for c in cards)


# --- routes --------------------------------------------------------------
class MessageIn(BaseModel):
    content: str


class InterruptIn(BaseModel):
    pass


@router.get("/tasks/{task_id}/messages")
async def get_messages(task_id: str):
    return {"messages": db.get_messages(task_id)}


@router.post("/tasks/{task_id}/messages")
async def post_message(task_id: str, body: MessageIn):
    if not db.get_task(task_id):
        from fastapi import HTTPException
        raise HTTPException(404, "task not found")
    if db.is_running(task_id):
        from fastapi import HTTPException
        raise HTTPException(409, "a run is already active for this task")
    # store the user message first
    db.append_message(task_id, "user", body.content)
    # start the agent run in the background
    asyncio.create_task(_run(task_id, body.content))
    return {"accepted": True}


@router.post("/tasks/{task_id}/interrupt")
async def interrupt(task_id: str):
    await SESSIONS.interrupt(task_id)
    return {"accepted": True}


@router.get("/tasks/{task_id}/events")
async def events(task_id: str, request: Request, after_seq: int = 0):
    async def gen() -> AsyncIterator[str]:
        q = await asyncio.shield(_subscribe(task_id))
        # replay missed events (reconnect-safe)
        if after_seq < _SEQ[task_id]:
            for ev in _EVENTS[task_id]:
                if ev["seq"] > after_seq:
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _SUBS[task_id].discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
