"""Preview router: real generated-agent process lifecycle exposed to the UI.

The Builder agent also has MCP `start_preview`/`stop_preview` tools; this router
is the UI-facing equivalent (status/start/stop). A preview only reports `running`
after a real subprocess answered HTTP — never faked.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from .. import config, db
from ..preview import PREVIEWS
from ..workspace import Workspace

router = APIRouter(prefix="/api", tags=["preview"])

# Hop-by-hop headers must not be forwarded by a proxy (RFC 7230 §6.1). We also
# drop host/content-length so httpx/Uvicorn set correct values for the hop.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "accept-encoding",
}
_PROXY_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _request_host(request: Request) -> str:
    """The host the browser used to reach the dashboard (strip the port)."""
    host = request.headers.get("host") or "127.0.0.1"
    return host.split(":")[0]


def _public_state(task_id: str, request: Request) -> dict:
    st = PREVIEWS.get(task_id)
    state = st.status if st.status != "failed" else "error"
    running = st.status == "running" and bool(st.port)
    # Direct URL uses the browser's host (works when the browser can reach the
    # preview port directly, e.g. same LAN).
    url = f"http://{_request_host(request)}:{st.port}" if running else None
    # Same-origin proxy path: works through SSH tunnels / any remote access, since
    # it is served by the dashboard's own origin and needs no extra port forwarded.
    proxy_url = f"/api/tasks/{task_id}/preview/proxy/" if running else None
    return {"state": state, "url": url, "proxy_url": proxy_url,
            "error": st.error or "", "pid": st.pid, "port": st.port}


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


@router.get("/tasks/{task_id}/preview/proxy")
def preview_proxy_no_slash(task_id: str):
    """Redirect to the trailing-slash form so the UI's relative ./assets and
    ./api/* URLs resolve against the proxy prefix (document URL must end in /)."""
    return RedirectResponse(url=f"/api/tasks/{task_id}/preview/proxy/", status_code=307)


@router.api_route("/tasks/{task_id}/preview/proxy/{path:path}", methods=_PROXY_METHODS)
async def preview_proxy(task_id: str, path: str, request: Request):
    """Same-origin reverse proxy to the real preview process.

    The iframe loads this path, so the Generated Agent is reachable no matter how
    the browser reached the dashboard (LAN IP, localhost, SSH tunnel) — only the
    dashboard origin/port needs to be reachable, never the random preview port.
    """
    st = PREVIEWS.get(task_id)
    if st.status != "running" or not st.port:
        raise HTTPException(409, "预览未运行，请先启动")

    target = f"http://127.0.0.1:{st.port}/{path}"
    if request.url.query:
        target += "?" + request.url.query

    body = await request.body()
    fwd = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=None, write=300.0, pool=10.0))
    try:
        upstream_req = client.build_request(request.method, target, headers=fwd, content=body)
        upstream = await client.send(upstream_req, stream=True)
    except Exception as e:
        await client.aclose()
        raise HTTPException(502, f"无法连接预览进程：{type(e).__name__}: {e}")

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}
    if "text/event-stream" in (upstream.headers.get("content-type") or ""):
        out_headers["X-Accel-Buffering"] = "no"

    async def _stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(_stream(), status_code=upstream.status_code, headers=out_headers)
