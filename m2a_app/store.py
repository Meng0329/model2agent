"""Local JSON-file persistence for settings, tasks and session associations.

Not a database server, not a logging platform — only what the product needs to
survive restart: the selected device, and per-task metadata + SDK session id.
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path

from . import config


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


class Store:
    def __init__(self, data_dir: Path | None = None):
        self.dir = Path(data_dir) if data_dir else config.DATA_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.dir / "settings.json"
        self.tasks_path = self.dir / "tasks.json"

    # ---- settings ----
    def get_settings(self) -> dict:
        return _read(self.settings_path, {})

    def set_device(self, device_id: str) -> None:
        s = self.get_settings(); s["device_id"] = device_id
        s["device_set_at"] = time.time()
        _write(self.settings_path, s)

    def get_device(self) -> str | None:
        return self.get_settings().get("device_id")

    # ---- tasks ----
    def list_tasks(self) -> list[dict]:
        return _read(self.tasks_path, [])

    def get_task(self, task_id: str) -> dict | None:
        for t in self.list_tasks():
            if t["task_id"] == task_id:
                return t
        return None

    def create_task(self, name: str, goal: str, assets: list[str]) -> dict:
        task = {
            "task_id": uuid.uuid4().hex[:12],
            "name": name,
            "goal": goal,
            "assets": assets,
            "status": "created",
            "created_at": time.time(),
            "updated_at": time.time(),
            "session_id": None,
        }
        tasks = self.list_tasks()
        tasks.insert(0, task)
        _write(self.tasks_path, tasks)
        return task

    def update_task(self, task_id: str, **kw) -> dict | None:
        tasks = self.list_tasks()
        for i, t in enumerate(tasks):
            if t["task_id"] == task_id:
                t.update(kw); t["updated_at"] = time.time()
                tasks[i] = t
                _write(self.tasks_path, tasks)
                return t
        return None
