"""Export router: download the generated Agent project as a ZIP (no secrets).

Also runs an honest Docker verification gate (V2_DOCKER=1) — building the image,
booting the container, and running a REAL inference check. Without that gate the
status stays "unverified"; we never report success without a real check.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import db
from ..workspace import Workspace

router = APIRouter(prefix="/api", tags=["export"])

_DOCKER_GATE = os.getenv("V2_DOCKER", "") == "1"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@router.get("/tasks/{task_id}/export")
def export_zip(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    ws = Workspace(task_id)
    if not (ws.project / "config.json").exists():
        raise HTTPException(400, "尚未生成可导出项目")
    out = ws.root / "export.zip"
    ws.export_project_zip(out)
    return FileResponse(str(out), filename=f"{task_id}-agent.zip", media_type="application/zip")


@router.get("/tasks/{task_id}/export/status")
def export_status(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    proj = Workspace(task_id).project
    return {
        "has_project": (proj / "config.json").exists(),
        "has_dockerfile": (proj / "Dockerfile").exists(),
        "docker_status": task.get("docker_status", "unverified"),
        "docker_gate_enabled": _DOCKER_GATE,
    }


def _real_docker_verify(task_id: str, proj) -> dict:
    """Build → boot → real inference → stop. Returns verified/failed HONESTLY."""
    tag = f"m2a-agent-{task_id[:12]}"
    port = _free_port()
    cid = None
    stage = "build"
    try:
        r = subprocess.run(["docker", "build", "-t", tag, "."], cwd=str(proj),
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            db.update_task(task_id, docker_status="failed")
            return {"status": "failed", "stage": "build", "log": (r.stderr or r.stdout)[-1500:]}

        stage = "run"
        r2 = subprocess.run(["docker", "run", "-d", "--rm", "-p", f"127.0.0.1:{port}:7860", tag],
                            capture_output=True, text=True, timeout=180)
        if r2.returncode != 0:
            db.update_task(task_id, docker_status="failed")
            return {"status": "failed", "stage": "run", "log": (r2.stderr or r2.stdout)[-1500:]}
        cid = r2.stdout.strip()

        stage = "health"
        base = f"http://127.0.0.1:{port}"
        ok = False
        for _ in range(90):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=2)
                ok = True
                break
            except Exception:
                time.sleep(1)
        if not ok:
            db.update_task(task_id, docker_status="failed")
            return {"status": "failed", "stage": "health", "log": "container did not answer /api/health in 90s"}

        # REAL inference inside the container. Example args come from the project
        # config.json on the host (the /api/config surface does not expose examples).
        stage = "inference"
        local_cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        cap = local_cfg.get("default_capability") or (local_cfg.get("capabilities") or ["predict"])[0]
        examples = local_cfg.get("examples") or {}
        rec = (examples.get(cap) or [{}])[0]
        args = rec.get("args") or {}
        body = json.dumps({"capability": cap, "args": args}).encode()
        req = urllib.request.Request(base + "/api/model/run", data=body,
                                     headers={"Content-Type": "application/json"})
        out = json.loads(urllib.request.urlopen(req, timeout=180).read())
        if out.get("result") is None:
            db.update_task(task_id, docker_status="failed")
            return {"status": "failed", "stage": "inference", "log": "inference returned null"}
        db.update_task(task_id, docker_status="verified")
        return {"status": "verified", "slug": local_cfg.get("slug"), "capability": cap,
                "sample_result": out.get("result")}
    except Exception as e:
        db.update_task(task_id, docker_status="failed")
        return {"status": "failed", "stage": stage, "error": f"{type(e).__name__}: {e}"}
    finally:
        if cid:
            subprocess.run(["docker", "stop", cid], capture_output=True, timeout=90)
        subprocess.run(["docker", "rmi", tag], capture_output=True, timeout=120)


@router.post("/tasks/{task_id}/export/verify-docker")
def verify_docker(task_id: str):
    """Real Docker build + boot + inference, gated by V2_DOCKER=1.

    Without the gate, we do NOT claim success — status stays 'unverified'.
    """
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    proj = Workspace(task_id).project
    if not (proj / "Dockerfile").exists():
        db.update_task(task_id, docker_status="unverified")
        raise HTTPException(400, "无 Dockerfile，无法验证")

    if not _DOCKER_GATE:
        db.update_task(task_id, docker_status="unverified")
        return {"status": "unverified", "note": "V2_DOCKER=1 未设置，跳过真实构建验证"}

    result = _real_docker_verify(task_id, proj)
    return result
