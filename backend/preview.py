"""Preview process lifecycle for generated Model Agents.

Runs a Generated Agent as an independent subprocess on a real free port and
tracks its state. One preview per task; switching tasks stops the old preview.
The UI embeds the live URL. Nothing here fakes a preview — a preview only
exists after a real process actually started and answered an HTTP check.
"""
from __future__ import annotations
import os
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field

from . import config


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@dataclass
class PreviewState:
    task_id: str
    pid: int | None = None
    port: int | None = None
    url: str | None = None
    status: str = "stopped"          # stopped | starting | running | failed
    error: str = ""
    version: str = "latest"
    started_at: float = 0.0


class PreviewManager:
    def __init__(self):
        self._previews: dict[str, PreviewState] = {}

    def get(self, task_id: str) -> PreviewState:
        return self._previews.get(task_id, PreviewState(task_id))

    def is_running(self, task_id: str) -> bool:
        p = self._previews.get(task_id)
        if not p or p.pid is None:
            return False
        try:
            os.kill(p.pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def start(self, task_id: str, entry: str, device: str = "cuda:0", env: dict | None = None,
              host: str = "127.0.0.1") -> PreviewState:
        """Launch the generated agent as an independent process on the SAVED device.

        `device` is e.g. "cuda:0" or "cpu" — we derive the CUDA_VISIBLE_DEVICES index
        so the preview runs on the device the user actually selected (no hardcoded GPU 0).

        `host` is the host the BROWSER used to reach the dashboard; the preview binds
        to 0.0.0.0, so the iframe must be served from that same host (not 127.0.0.1,
        which would point at the user's own machine for a remote browser).
        """
        self.stop(task_id)
        port = free_port()
        st = PreviewState(task_id, pid=None, port=port,
                          url=f"http://{host}:{port}", status="starting")
        self._previews[task_id] = st
        e = dict(os.environ)
        cuda_idx = device.split(":")[-1] if device.startswith("cuda:") else "-1"
        e["CUDA_VISIBLE_DEVICES"] = cuda_idx
        e["M2A_PREVIEW_DEVICE"] = device
        e["M2A_PREVIEW_PORT"] = str(port)
        if env:
            e.update(env)
        try:
            proc = subprocess.Popen(
                ["python3", entry, "--port", str(port)],
                cwd=os.path.dirname(entry) or ".",
                env=e,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            st.pid = proc.pid
        except Exception as ex:
            st.status = "failed"
            st.error = f"{type(ex).__name__}: {ex}"
            return st
        # wait for the app to actually answer (real check, not a fake) — always via
        # loopback, independent of the public host the iframe will use
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                st.status = "failed"
                st.error = f"process exited rc={proc.returncode}"
                return st
            if self._http_ok(f"http://127.0.0.1:{port}/api/health"):
                st.status = "running"
                st.started_at = time.time()
                return st
            time.sleep(0.5)
        st.status = "failed"
        st.error = "preview did not answer within 30s"
        return st

    @staticmethod
    def _http_ok(url: str) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def stop(self, task_id: str) -> None:
        p = self._previews.get(task_id)
        if p and p.pid:
            try:
                proc = subprocess.Popen(["kill", "-TERM", str(p.pid)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait(timeout=5)
            except Exception:
                pass
            p.pid = None
        if p:
            p.status = "stopped"
            p.error = ""

    def stop_all_except(self, keep_task_id: str | None) -> None:
        for tid in list(self._previews):
            if tid != keep_task_id:
                self.stop(tid)


PREVIEWS = PreviewManager()
