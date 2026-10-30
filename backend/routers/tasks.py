"""Task CRUD + asset intake. Creates an isolated workspace per task."""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from .. import config, db
from ..workspace import Workspace

router = APIRouter(prefix="/api", tags=["tasks"])


class TaskPatch(BaseModel):
    name: str | None = None
    goal: str | None = None


def _detect_asset_slug(inputs: Path) -> str:
    """Lightweight asset detection (full analysis happens in the Builder/generator)."""
    for m in inputs.rglob("manifest.json"):
        try:
            j = json.loads(m.read_text(encoding="utf-8"))
            if j.get("slug"):
                return str(j["slug"])
        except Exception:
            pass
    for f in inputs.rglob("infer.py"):
        return f.parent.name
    return "custom"


def _public(t: dict) -> dict:
    """Strip nothing sensitive; add convenience flags."""
    t = dict(t)
    t["has_generated"] = bool(t.get("has_generated"))
    return t


@router.get("/tasks")
def list_tasks():
    return [_public(t) for t in db.list_tasks()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    t = db.get_task(task_id)
    if not t:
        raise HTTPException(404, "task not found")
    return _public(t)


@router.post("/tasks")
async def create_task(
    name: str = Form(...),
    goal: str = Form(""),
    device: str = Form(""),
    files: list[UploadFile] = File(...),
):
    config.ensure_dirs()
    ws = Workspace(db.new_id()).create()
    task = db.create_task(name, goal, device or db.get_setting("device", ""))
    # re-key the workspace dir to the new task id
    old_root = ws.root
    ws = Workspace(task["id"]).create()
    if old_root.exists():
        shutil.rmtree(old_root)

    saved = []
    for f in files:
        if not f.filename:
            continue
        dest = ws.inputs / Path(f.filename).name
        with dest.open("wb") as out:
            while chunk := await f.read(1024 * 1024):
                out.write(chunk)
        saved.append(dest)

    # extract any zip archives safely
    for dest in saved:
        if dest.suffix.lower() == ".zip":
            ws.add_asset_zip(dest, extract=True)

    slug = _detect_asset_slug(ws.inputs)
    db.update_task(task["id"], asset_slug=slug, status="created",
                   workspace_path=str(ws.root))
    return _public(db.get_task(task["id"]))


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, body: TaskPatch):
    if not db.get_task(task_id):
        raise HTTPException(404, "task not found")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        db.update_task(task_id, **fields)
    return _public(db.get_task(task_id))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    if not db.get_task(task_id):
        raise HTTPException(404, "task not found")
    from ..preview import PREVIEWS
    try:
        PREVIEWS.stop(task_id)
    except Exception:
        pass
    from ..agent_bridge import SESSIONS
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(SESSIONS.close(task_id))
    except Exception:
        pass
    ws = Workspace(task_id)
    if ws.root.exists():
        shutil.rmtree(ws.root, ignore_errors=True)
    db.delete_task(task_id)
    return {"ok": True}
