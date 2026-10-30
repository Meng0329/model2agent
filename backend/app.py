"""Model2Agent V2.0 FastAPI application entrypoint (Product layer)."""
from __future__ import annotations
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db
from .routers import devices, tasks, chat, workspace
from .workspace import start_watcher

app = FastAPI(title="Model2Agent V2.0", version="2.0.0")
config.ensure_dirs()
db.init()
start_watcher()

# CORS for the Vite dev server during development. Lock down in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router)
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(workspace.router)


@app.get("/api/health")
def health():
    return {"ok": True, "model": config.DEEPSEEK_MODEL, "base_url": config.ANTHROPIC_BASE_URL}


# Serve the production frontend build (dist/) when present.
_DIST = config.FRONTEND_DIST
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
