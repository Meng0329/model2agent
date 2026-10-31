#!/usr/bin/env python3
"""Model2Agent V2.0 — acceptance harness (real checks, honest SKIPs).

Runs the product gates against a live backend and reports PASS/SKIP/FAIL with
verbatim evidence. Nothing here fabricates success: Docker verification is
SKIP'd unless V2_DOCKER=1 (in which case it really builds + boots + infers).

Usage:
    python3 scripts/v2_acceptance.py              # against http://127.0.0.1:8100
    M2A_BASE=http://<host>:8100 python3 scripts/v2_acceptance.py
    V2_DOCKER=1 python3 scripts/v2_acceptance.py  # also run the real Docker gate

Exit code: 0 if no FAIL, 1 otherwise.
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE = os.getenv("M2A_BASE", "http://127.0.0.1:8100").rstrip("/")
REPO = Path(__file__).resolve().parent.parent


class Skip(Exception):
    pass


_results: list[tuple[str, str, str]] = []


def check(name: str, fn):
    try:
        detail = fn()
        results_list = _results
        results_list.append((name, "PASS", detail or ""))
    except Skip as e:
        _results.append((name, "SKIP", str(e)))
    except Exception as e:
        _results.append((name, "FAIL", f"{type(e).__name__}: {e}"))


def _get(path: str, timeout: int = 15):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=timeout).read())


def _post(path: str, body=None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def _reachable(url: str, timeout: int = 4) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# --- gates -----------------------------------------------------------------

def g_health():
    h = _get("/api/health", 10)
    assert h.get("ok"), f"health not ok: {h}"
    return f"model={h.get('model')} base={h.get('base_url')}"


def g_devices():
    d = _get("/api/devices", 10)
    devs = d if isinstance(d, list) else d.get("devices", [])
    assert devs, "no devices detected"
    gpus = [x for x in devs if str(x.get("name", "")).upper().count("GPU") or "cuda" in str(x.get("type", ""))]
    return f"{len(devs)} device(s): " + ", ".join(x.get("name", x.get("id", "?")) for x in devs[:4])


def _pick_generated_task() -> tuple[str, Path]:
    """Find a task whose project/config.json exists on disk."""
    tasks = _get("/api/tasks")
    for t in tasks:
        if not t.get("has_generated"):
            continue
        proj = REPO / "m2a_data" / "workspaces" / t["id"] / "project"
        if (proj / "config.json").exists() and (proj / "run.py").exists():
            return t["id"], proj
    raise Skip("no task with a generated project found (run the Builder once first)")


def g_selfcheck():
    tid, proj = _pick_generated_task()
    r = subprocess.run([sys.executable, "model_exec.py"], cwd=str(proj),
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"selfcheck rc={r.returncode}: {r.stderr.strip()[:300]}")
    out = json.loads(r.stdout)
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    # require at least one real numeric prediction
    has_pred = any(isinstance(v, (int, float)) for v in out.values())
    assert has_pred, f"no numeric prediction in selfcheck: {out}"
    return f"task={tid} slug={cfg.get('slug')} capabilities={list(out.keys())}"


def g_preview():
    tid, _ = _pick_generated_task()
    _post(f"/api/tasks/{tid}/preview/stop", {}, 60)  # ensure clean start
    st = json.loads(_post(f"/api/tasks/{tid}/preview/start", {}, 60).read())
    assert st.get("state") == "running", f"preview not running: {st}"
    url = st.get("url")
    assert url and _reachable(url + "/api/health"), f"preview url unreachable: {url}"
    # task-switch should stop the old one — start a no-op second preview on same task (restart) is fine;
    # we just stop here to leave it clean
    _post(f"/api/tasks/{tid}/preview/stop", {}, 60)
    return f"started+health+stopped on {url}"


def g_export_zip():
    import re
    tid, _ = _pick_generated_task()
    req = urllib.request.Request(f"{BASE}/api/tasks/{tid}/export")
    data = urllib.request.urlopen(req, timeout=60).read()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        tf.write(data)
        zp = Path(tf.name)
    try:
        z = zipfile.ZipFile(zp)
        names = z.namelist()
        assert any(n.endswith("config.json") for n in names), "config.json missing"
        assert any(n.endswith("Dockerfile") for n in names), "Dockerfile missing"
        assert any(n.endswith(".pt") or n.endswith(".json") and "model" in n for n in names), "weights missing"

        # secret scan: prefer the REAL key value from repo .env for an exact match;
        # otherwise use a strict key-shape regex. .env.example is a documented
        # placeholder file and is intentionally shipped, so it is not a leak.
        real_key = None
        envf = REPO / ".env"
        if envf.exists():
            for line in envf.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(("ANTHROPIC_API_KEY=", "DEEPSEEK_API_KEY=")):
                    real_key = line.split("=", 1)[1].strip().strip('"').encode()
                    break
        key_re = re.compile(rb"sk-[A-Za-z0-9]{24,}")
        leaks = [n for n in names if n.split("/")[-1] in (".env", ".env.local", ".credentials.json")]
        assert not leaks, f"secret files in zip: {leaks}"
        key_hit = []
        for n in names:
            if n.endswith(".env.example"):
                continue  # placeholder by design
            blob = z.read(n)
            if real_key and real_key in blob:
                key_hit.append(n)
            elif not real_key and key_re.search(blob):
                key_hit.append(n)
        assert not key_hit, f"real secret leaked into: {key_hit}"
        return f"{len(names)} files, no secret files, no real key, has Dockerfile+config+weights"
    finally:
        zp.unlink(missing_ok=True)


def g_docker():
    if os.getenv("V2_DOCKER") != "1":
        raise Skip("V2_DOCKER=1 not set — real Docker build/boot/inference skipped (status stays unverified)")
    tid, _ = _pick_generated_task()
    # The backend's verify-docker does the real build+run+inference; call it (slow).
    out = json.loads(_post(f"/api/tasks/{tid}/export/verify-docker", {}, timeout=600).read())
    if out.get("status") != "verified":
        raise RuntimeError(f"docker verify did not pass: {out}")
    return f"verified (sample_result={out.get('sample_result')})"


# --- run + report ----------------------------------------------------------

def main():
    checks = [
        ("A  backend health", g_health),
        ("B  real device detection", g_devices),
        ("C  generated project real selfcheck", g_selfcheck),
        ("D  preview real process + reachability", g_preview),
        ("E  export ZIP (secret-free, complete)", g_export_zip),
        ("F  Docker verify (gated)", g_docker),
    ]
    for name, fn in checks:
        check(name, fn)

    print("\n=== Model2Agent V2.0 acceptance ===")
    width = max(len(n) for n, *_ in _results)
    fails = 0
    for name, status, detail in _results:
        print(f"  {name.ljust(width)}  {status:4}  {detail}")
        if status == "FAIL":
            fails += 1
    print(f"\n{'FAIL' if fails else 'PASS'} — {len(_results)} checks, {fails} failed, "
          f"{sum(1 for _, s, _ in _results if s == 'SKIP')} skipped")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
