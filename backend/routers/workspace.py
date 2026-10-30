"""Workspace file API: tree, content, state. Task-isolated, path-traversal-safe."""
from __future__ import annotations
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import db
from ..workspace import Workspace

router = APIRouter(prefix="/api", tags=["workspace"])

TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt", ".yaml", ".yml",
            ".css", ".html", ".sh", ".toml", ".ini", ".cfg", ".csv", ".env.example", ".dockerignore"}
BIN_EXT = {".pt", ".pth", ".joblib", ".model", ".bin", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".onnx", ".h5", ".pkl", ".npz", ".so", ".whl"}


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


@router.get("/tasks/{task_id}/files")
async def list_files(task_id: str):
    if not db.get_task(task_id):
        raise HTTPException(404, "task not found")
    ws = Workspace(task_id)
    items = []
    if ws.root.exists():
        for p in sorted(ws.root.rglob("*")):
            if _is_hidden(p.relative_to(ws.root)):
                continue
            if p.is_dir():
                items.append({"path": str(p.relative_to(ws.root)), "name": p.name, "is_dir": True, "size": 0})
            else:
                items.append({"path": str(p.relative_to(ws.root)), "name": p.name, "is_dir": False,
                              "size": p.stat().st_size,
                              "ext": p.suffix.lower(),
                              "is_text": p.suffix.lower() in TEXT_EXT})
    return {"files": items}


@router.get("/tasks/{task_id}/files/content")
async def file_content(task_id: str, path: str):
    if not db.get_task(task_id):
        raise HTTPException(404, "task not found")
    ws = Workspace(task_id)
    try:
        fp = ws.safe_path(path)
    except ValueError:
        raise HTTPException(400, "invalid path")
    if not fp.exists() or fp.is_dir():
        raise HTTPException(404, "file not found")
    if fp.suffix.lower() in BIN_EXT:
        return {"path": path, "content": "", "size": fp.stat().st_size, "is_binary": True}
    try:
        content = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        content = ""
    return {"path": path, "content": content, "size": fp.stat().st_size, "is_binary": False}


@router.get("/tasks/{task_id}/workspace/state")
async def workspace_state(task_id: str):
    ws = Workspace(task_id)
    files = []
    if ws.root.exists():
        files = [str(p.relative_to(ws.root)) for p in ws.root.rglob("*") if p.is_file() and not _is_hidden(p.relative_to(ws.root))]
    return {"state": "ready", "task_id": task_id, "file_count": len(files)}
