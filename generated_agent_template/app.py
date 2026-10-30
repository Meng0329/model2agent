"""Generated Model Agent — FastAPI server.

Endpoints:
  GET  /api/health                       -> liveness (used by Builder preview)
  GET  /api/config                       -> model config (input_type, capabilities, labels)
  POST /api/model/run                    -> direct real inference (capability + args)
  POST /api/upload                       -> upload image/CSV, returns adapted features
  POST /api/chat                         -> SSE chat turn (own SDK session, per sid)
  POST /api/interrupt                    -> interrupt the active chat turn for a sid
Serves the React UI from ./web/dist when present.
"""
from __future__ import annotations
import asyncio
import json
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import model_exec
import adapters
import agent_core
from agent_core import SESSIONS

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

app = FastAPI(title=f"Model2Agent · {CFG['slug']}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# per-session event buses (sid -> events) for chat SSE
_EV: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
_SUB: dict[str, set[asyncio.Queue]] = defaultdict(set)
_SEQ: dict[str, int] = defaultdict(int)


def _pub(sid: str, ev: dict) -> None:
    _SEQ[sid] += 1
    ev = {**ev, "seq": _SEQ[sid]}
    _EV[sid].append(ev)
    for q in list(_SUB[sid]):
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            _SUB[sid].discard(q)


@app.get("/api/health")
def health():
    return {"ok": True, "slug": CFG["slug"], "input_type": CFG["input_type"]}


@app.get("/api/config")
def get_config():
    return {k: CFG.get(k) for k in ("slug", "model_id", "framework", "input_type", "adapter",
                                    "vector_len", "feature_names", "labels", "capabilities", "default_capability")}


class RunIn(BaseModel):
    capability: str
    args: dict = {}


@app.post("/api/model/run")
def model_run(body: RunIn):
    out = model_exec.run(body.capability, body.args or {})
    return {"capability": body.capability, "result": out}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), sid: str = ""):
    data = await file.read()
    it = CFG.get("input_type")
    if it == "image":
        feats = adapters.image_to_features(data)
        out = {"input_type": "image", "features": feats, "vector_len": len(feats)}
    elif it == "tabular":
        rows = adapters.tabular_rows_to_features(data)
        out = {"input_type": "tabular", "rows": rows}
    else:
        return {"input_type": it, "note": "no adapter for this input type"}
    if sid:
        agent_core.ATTACHMENTS[sid] = out
    return out


class ChatIn(BaseModel):
    sid: str
    content: str
    attachment: dict | None = None


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    sid = body.sid or uuid.uuid4().hex

    async def gen():
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        _SUB[sid].add(q)
        _pub(sid, {"type": "run_started"})
        sess = await SESSIONS.get(sid)
        finished: asyncio.Event = asyncio.Event()

        async def pump():
            try:
                async for ev in sess.respond(body.content, body.attachment):
                    if ev.get("type") == "text":
                        _pub(sid, {"type": "text_delta", "text": ev["text"]})
                    elif ev.get("type") == "tool":
                        st = ev.get("status")
                        _pub(sid, {"type": ("tool_started" if st == "running" else
                                            ("tool_failed" if st == "error" else "tool_completed")),
                                   "card_id": ev.get("card_id"), "name": ev.get("name"),
                                   "status": st, "input": ev.get("input", ""),
                                   "result": ev.get("result", "")})
                    elif ev.get("type") == "result":
                        _pub(sid, {"type": "run_completed", "text": ev.get("text", ""),
                                   "is_error": bool(ev.get("is_error"))})
            finally:
                finished.set()

        pump_task = asyncio.create_task(pump())
        try:
            # stream frames while the agent runs; then drain remaining and close
            while not finished.is_set():
                try:
                    e = await asyncio.wait_for(q.get(), timeout=1)
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keepalive\n\n"
            while not q.empty():
                e = q.get_nowait()
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
        finally:
            _SUB[sid].discard(q)
            # keep the SDK session alive between turns (multi-turn context);
            # it is only torn down by /api/interrupt (explicit stop) or shutdown.
            if not finished.is_set():
                pump_task.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/interrupt")
async def interrupt(sid: str = ""):
    if sid:
        sess = await SESSIONS.get(sid)
        await sess.interrupt()
        await SESSIONS.close(sid)
    return {"ok": True}


# serve React build
_dist = HERE / "web" / "dist"
if _dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="web")
