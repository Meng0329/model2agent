"""Preview router: real generated-agent process lifecycle exposed to the UI.

The Builder agent also has MCP `start_preview`/`stop_preview` tools; this router
is the UI-facing equivalent (status/start/stop). A preview only reports `running`
after a real subprocess answered HTTP — never faked.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import config, db
from ..preview import PREVIEWS
from ..workspace import Workspace

router = APIRouter(prefix="/api", tags=["preview"])


def _request_host(request: Request) -> str:
    """The host the browser used to reach the dashboard (strip the port)."""
    host = request.headers.get("host") or "127.0.0.1"
    return host.split(":")[0]


def _public_state(task_id: str, request: Request) -> dict:
    st = PREVIEWS.get(task_id)
    state = st.status if st.status != "failed" else "error"
    # iframe URL must use the browser's host, not loopback, so a remote browser can
    # actually reach the preview (which binds to 0.0.0.0)
    url = f"http://{_request_host(request)}:{st.port}" if (st.status == "running" and st.port) else None
    return {"state": state, "url": url, "error": st.error or "", "pid": st.pid, "port": st.port}


@router.get("/tasks/{task_id}/preview/status")
def preview_status(task_id: str, request: Request):
    if not db.get_task(task_id):
        raise HTTPException(404, "task not found")
    s = _public_state(task_id, request)
    db.update_task(task_id, preview_state=s["state"], preview_url=s["url"] or "", preview_error=s["error"])
    return s


@router.post("/tasks/{task_id}/preview/start")
def preview_start(task_id: str, request: Request):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    proj = Workspace(task_id).project
    entry = proj / "run.py"
    if not entry.exists():
        raise HTTPException(400, "尚未生成可运行项目（project/run.py 不存在）")
    # one active preview at a time: switching tasks stops the old process
    PREVIEWS.stop_all_except(task_id)
    device = db.get_setting("device", "") or task.get("device") or "cuda:0"
    host = _request_host(request)
    st = PREVIEWS.start(task_id, str(entry), device=device, env=config.agent_env(), host=host)
    s = _public_state(task_id, request)
    db.update_task(task_id, preview_state=s["state"], preview_url=s["url"] or "", preview_error=s["error"])
    if s["state"] == "error":
        raise HTTPException(500, s["error"] or "preview failed to start")
    return s


@router.post("/tasks/{task_id}/preview/stop")
def preview_stop(task_id: str):
    PREVIEWS.stop(task_id)
    db.update_task(task_id, preview_state="stopped", preview_url="", preview_error="")
    return {"state": "stopped"}
