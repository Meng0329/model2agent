"""CLI entrypoint for the deterministic generation step.

The Builder agent runs this via Bash (from the agent-generation skill) after it
has decided the asset to build. Execution here is deterministic Python that
scaffolds the React+FastAPI project, copies real weights, writes config.json.

Usage:
    python -m backend.gen_cli generate <task_id> <asset_dir> [--labels a,b,c]
    python -m backend.gen_cli selfcheck <task_id>     # run generated agent's selfcheck
    python -m backend.gen_cli verify <task_id>        # boot generated agent + health + real run
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def cmd_generate(args) -> int:
    from .generator import generate
    labels = args.labels.split(",") if args.labels else None
    proj = generate(args.task_id, args.asset_dir)
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "ok": True, "project": str(proj), "slug": cfg["slug"],
        "input_type": cfg["input_type"], "adapter": cfg["adapter"],
        "capabilities": cfg["capabilities"], "vector_len": cfg["vector_len"],
        "labels": cfg.get("labels", []),
    }, ensure_ascii=False))
    return 0


def cmd_selfcheck(args) -> int:
    from .workspace import Workspace
    proj = Workspace(args.task_id).project
    import subprocess
    r = subprocess.run([sys.executable, str(proj / "model_exec.py")],
                       capture_output=True, text=True, cwd=str(proj), timeout=180)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


def cmd_verify(args) -> int:
    """Boot the generated agent, hit health + real predict, then stop."""
    import socket, subprocess, time, urllib.request
    from .workspace import Workspace
    proj = Workspace(args.task_id).project
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([sys.executable, "run.py", "--port", str(port)],
                            cwd=str(proj), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}"
        ok = False
        for _ in range(30):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                ok = True; break
            except Exception:
                time.sleep(0.5)
        if not ok:
            print(json.dumps({"ok": False, "error": "generated agent did not boot"})); return 1
        cfg = json.loads(urllib.request.urlopen(base + "/api/config", timeout=3).read())
        # real inference: run selfcheck via model_exec
        selfcheck = json.loads(subprocess.run(
            [sys.executable, "model_exec.py"], cwd=str(proj), capture_output=True, text=True,
            timeout=180).stdout)
        print(json.dumps({"ok": True, "slug": cfg.get("slug"),
                          "input_type": cfg.get("input_type"), "selfcheck": selfcheck},
                         ensure_ascii=False, default=str))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("task_id"); g.add_argument("asset_dir"); g.add_argument("--labels", default=None); g.set_defaults(fn=cmd_generate)
    sc = sub.add_parser("selfcheck"); sc.add_argument("task_id"); sc.set_defaults(fn=cmd_selfcheck)
    v = sub.add_parser("verify"); v.add_argument("task_id"); v.set_defaults(fn=cmd_verify)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
