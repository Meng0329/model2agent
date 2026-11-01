"""Generated Model Agent — FastAPI server (model-agnostic runtime).

Endpoints:
  GET  /api/health
  GET  /api/config                     -> model config + agent_ui
  GET  /api/conversations              -> conversation list
  POST /api/conversations              -> create a conversation
  GET  /api/conversations/{cid}/messages
  POST /api/conversations/{cid}/clear
  DELETE /api/conversations/{cid}
  POST /api/upload                     -> adapt input, returns real preprocess trace
  POST /api/model/run                  -> real inference (+ optional trace)
  GET  /api/apidocs                    -> docs generated from the real routes/config
  POST /api/chat                       -> SSE chat turn persisted per conversation
  POST /api/interrupt                  -> interrupt a conversation's active turn
Serves the React UI from ./web/dist when present.
"""
from __future__ import annotations
import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import model_exec
import adapters
import agent_core
import store
from agent_core import SESSIONS

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
UI_FILE = HERE / "agent_ui.json"
UI = json.loads(UI_FILE.read_text(encoding="utf-8")) if UI_FILE.exists() else {}

app = FastAPI(
    title=f"Model2Agent · {CFG['slug']}",
    description=f"真实模型 {CFG['slug']} 的 Agent API（推理结果来自真实权重）。",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_EV: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
_SUB: dict[str, set[asyncio.Queue]] = defaultdict(set)
_SEQ: dict[str, int] = defaultdict(int)


def _pub(cid: str, ev: dict) -> None:
    _SEQ[cid] += 1
    ev = {**ev, "seq": _SEQ[cid]}
    _EV[cid].append(ev)
    for q in list(_SUB[cid]):
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            _SUB[cid].discard(q)


@app.get("/api/health")
def health():
    return {"ok": True, "slug": CFG["slug"], "input_type": CFG["input_type"]}


@app.get("/api/config")
def get_config():
    out = {k: CFG.get(k) for k in (
        "slug", "model_id", "framework", "input_type", "adapter", "vector_len",
        "feature_names", "labels", "capabilities", "default_capability",
        "image_preprocess")}
    out["agent_ui"] = UI
    return out


# ---- conversations -------------------------------------------------------
@app.get("/api/conversations")
def conversations():
    return {"conversations": store.list_conversations()}


class ConversationIn(BaseModel):
    title: str | None = None


@app.post("/api/conversations")
def create_conversation(body: ConversationIn | None = None):
    return store.create_conversation(body.title if body else None)


@app.get("/api/conversations/{cid}/messages")
def conversation_messages(cid: str):
    return {"conversation_id": cid, "messages": store.get_messages(cid)}


@app.post("/api/conversations/{cid}/clear")
def clear_conversation(cid: str):
    if not store.clear_conversation(cid):
        raise HTTPException(404, "conversation not found")
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: str):
    if not store.delete_conversation(cid):
        raise HTTPException(404, "conversation not found")
    return {"ok": True}


# ---- inference -----------------------------------------------------------
class RunIn(BaseModel):
    capability: str
    args: dict = {}
    trace: bool = False


def _trace(capability: str, args: dict, elapsed_ms: float) -> dict:
    feats = args.get("features")
    mode = CFG.get("input_type")
    base = {"capability": capability, "input_type": mode, "latency_ms": round(elapsed_ms, 2),
            "labels": CFG.get("labels")}
    if mode == "image" and isinstance(feats, list) and CFG.get("image_preprocess"):
        n = int(CFG["image_preprocess"]["canvas"][0])
        if len(feats) == n * n:
            base["grid"] = [[float(v) for v in feats[r * n:(r + 1) * n]] for r in range(n)]
    if mode == "tabular" and isinstance(feats, list):
        base["features"] = feats
        base["feature_names"] = CFG.get("feature_names")
    return base


@app.post("/api/model/run")
def model_run(body: RunIn):
    t0 = time.perf_counter()
    out = model_exec.run(body.capability, body.args or {})
    resp = {"capability": body.capability, "result": out}
    if body.trace:
        resp["trace"] = _trace(body.capability, body.args or {}, (time.perf_counter() - t0) * 1000)
    return resp


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), conversation_id: str = "", sid: str = ""):
    data = await file.read()
    key = conversation_id or sid
    it = CFG.get("input_type")
    # Persist the raw upload so a misclassification can be reproduced/diagnosed
    # from the exact bytes (kept inside the project; excluded from the ZIP).
    saved = ""
    try:
        ext = (Path(file.filename or "upload").suffix or ".bin").lower()
        uroot = HERE / "uploads" / (key or "anon")
        uroot.mkdir(parents=True, exist_ok=True)
        path = uroot / f"{int(time.time())}{ext}"
        path.write_bytes(data)
        saved = str(path.relative_to(HERE))
    except Exception:
        saved = ""
    if it == "image":
        feats, trace = adapters.image_to_features_with_trace(data)
        out = {"input_type": "image", "features": feats, "vector_len": len(feats), "trace": trace}
    elif it == "tabular":
        rows = adapters.tabular_rows_to_features(data)
        out = {"input_type": "tabular", "rows": rows}
    else:
        raise HTTPException(400, f"no upload adapter for input_type={it}")
    if saved:
        out["saved"] = saved
    if key:
        agent_core.ATTACHMENTS[key] = out
    return out


# ---- API docs ------------------------------------------------------------
def _snippet(method: str, path: str, body: dict | None) -> dict:
    b = json.dumps(body, ensure_ascii=False) if body is not None else ""
    curl = f"curl -X {method} 'http://localhost:7860{path}'"
    if body is not None:
        curl += f" -H 'Content-Type: application/json' -d '{b}'"
    py = (f"import requests\nr = requests.{method.lower()}(\n"
          f"    'http://localhost:7860{path}',\n"
          + (f"    json={b},\n" if body is not None else "")
          + ")\nprint(r.json())")
    js = (f"const r = await fetch('http://localhost:7860{path}', {{\n"
          f"  method: '{method}',\n"
          + ("  headers: { 'Content-Type': 'application/json' },\n" if body is not None else "")
          + (f"  body: JSON.stringify({b}),\n" if body is not None else "")
          + "});\nconsole.log(await r.json());")
    return {"curl": curl, "python": py, "javascript": js}


@app.get("/api/apidocs")
def apidocs():
    sample = (UI.get("input") or {}).get("sample")
    run_body = {"capability": CFG.get("default_capability"), "args": {"features": sample}}
    endpoints = [
        {"method": "GET", "path": "/api/health", "summary": "存活检查"},
        {"method": "GET", "path": "/api/config", "summary": "模型配置与 agent_ui"},
        {"method": "GET", "path": "/api/conversations", "summary": "会话列表"},
        {"method": "POST", "path": "/api/conversations",
         "summary": "创建会话", "request": {"title": "可选"}, "snippets": _snippet("POST", "/api/conversations", {"title": "示例会话"})},
        {"method": "GET", "path": "/api/conversations/{cid}/messages", "summary": "会话消息"},
        {"method": "POST", "path": "/api/model/run",
         "summary": "真实推理（可加 trace=true）",
         "request": {"capability": CFG.get("default_capability"), "args": {"features": "..."}, "trace": False},
         "snippets": _snippet("POST", "/api/model/run", run_body)},
        {"method": "POST", "path": "/api/upload",
         "summary": "上传图片/CSV 并转换为模型输入（multipart）",
         "request": "multipart/form-data: file"},
        {"method": "POST", "path": "/api/chat",
         "summary": "对话（SSE 流式）；body: {conversation_id, content, attachment}",
         "request": {"conversation_id": "<id>", "content": "这是什么数字？"}},
        {"method": "POST", "path": "/api/interrupt", "summary": "中断当前对话"},
    ]
    return {
        "title": f"{CFG['slug']} Agent API",
        "version": "2.0",
        "swagger": "/docs",
        "openapi": "/openapi.json",
        "model": UI.get("model") or {k: CFG.get(k) for k in (
            "slug", "framework", "input_type", "labels", "capabilities")},
        "endpoints": endpoints,
        "sse_events": ["run_started", "text_delta", "tool_started",
                       "tool_completed", "tool_failed", "model_run", "run_completed"],
    }


# ---- chat ----------------------------------------------------------------
class ChatIn(BaseModel):
    conversation_id: str | None = None
    sid: str | None = None
    content: str
    attachment: dict | None = None


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    cid = body.conversation_id or body.sid
    created = False
    if not cid:
        cid = store.create_conversation()["id"]
        created = True
    else:
        store.ensure_conversation(cid)

    # persist the user turn (with the real attachment summary)
    user_msg = store.append_message(cid, "user", body.content, attachment=body.attachment)
    assistant_msg = store.append_message(cid, "assistant", "")
    if created:
        title = body.content.strip().replace("\n", " ")[:24]
        if title:
            store.rename_conversation(cid, title)
    if body.attachment:
        agent_core.ATTACHMENTS[cid] = body.attachment

    async def gen():
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        _SUB[cid].add(q)
        _pub(cid, {"type": "run_started", "conversation_id": cid})
        sess = await SESSIONS.get(cid)
        finished: asyncio.Event = asyncio.Event()
        parts: list[str] = []
        cards: list[dict] = []

        async def pump():
            try:
                async for ev in sess.respond(body.content, body.attachment):
                    typ = ev.get("type")
                    if typ == "text":
                        parts.append(ev["text"])
                        _pub(cid, {"type": "text_delta", "text": ev["text"]})
                    elif typ == "tool":
                        st = ev.get("status")
                        card = {"id": ev.get("card_id"), "name": ev.get("name"),
                                "status": st, "input": ev.get("input", ""), "result": ev.get("result", "")}
                        idx = next((i for i, c in enumerate(cards) if c["id"] == card["id"]), None)
                        if idx is None:
                            cards.append(card)
                        else:
                            cards[idx].update(card)
                        _pub(cid, {"type": ("tool_started" if st == "running" else
                                            ("tool_failed" if st == "error" else "tool_completed")),
                                   "card_id": card["id"], "name": card["name"], "status": card["status"],
                                   "input": card["input"], "result": card["result"]})
                    elif typ == "model_run":
                        _pub(cid, {"type": "model_run", "capability": ev.get("capability"),
                                   "result": ev.get("result"), "trace": ev.get("trace")})
                    elif typ == "result":
                        _pub(cid, {"type": "run_completed", "text": ev.get("text", ""),
                                   "is_error": bool(ev.get("is_error")),
                                   "conversation_id": cid})
            finally:
                finished.set()

        pump_task = asyncio.create_task(pump())
        try:
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
            _SUB[cid].discard(q)
            store.update_message(cid, assistant_msg["id"], content="".join(parts), cards=cards)
            if not finished.is_set():
                pump_task.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/interrupt")
async def interrupt(conversation_id: str = "", sid: str = ""):
    key = conversation_id or sid
    if key:
        sess = await SESSIONS.get(key)
        await sess.interrupt()
        await SESSIONS.close(key)
    return {"ok": True}


# serve React build
_dist = HERE / "web" / "dist"
if _dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="web")
