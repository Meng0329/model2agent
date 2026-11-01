"""CLI entrypoint for deterministic generation + EVIDENCE-BASED verification.

The Builder agent runs this (or the MCP tools that wrap it) after generating.
Verification is model-agnostic: it exercises the produced agent's real HTTP API
and reports every check with its actual evidence. No fabricated successes.

Usage:
    python -m backend.gen_cli generate <task_id> <asset_dir>
    python -m backend.gen_cli selfcheck <task_id>
    python -m backend.gen_cli verify <task_id>        # prints the full report JSON
"""
from __future__ import annotations
import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def cmd_generate(args) -> int:
    from .generator import generate
    proj = generate(args.task_id, args.asset_dir)
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    ui = json.loads((proj / "agent_ui.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "ok": True, "project": str(proj), "slug": cfg["slug"],
        "input_type": cfg["input_type"], "adapter": cfg["adapter"],
        "capabilities": cfg["capabilities"], "vector_len": cfg["vector_len"],
        "labels": cfg.get("labels", []), "presets": ui.get("presets", []),
    }, ensure_ascii=False))
    return 0


def cmd_selfcheck(args) -> int:
    from .workspace import Workspace
    proj = Workspace(args.task_id).project
    r = subprocess.run([sys.executable, str(proj / "model_exec.py")],
                       capture_output=True, text=True, cwd=str(proj), timeout=180)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


# ---------------------------------------------------------------------------
# verification helpers
# ---------------------------------------------------------------------------
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get(base: str, path: str, timeout: float = 5):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read())


def _post(base: str, path: str, body: dict, timeout: float = 30):
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw.decode("utf-8", "replace")}


def _post_multipart(base: str, path: str, filename: str, content: bytes, timeout: float = 30):
    boundary = "----m2a" + str(int(time.time() * 1000))
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(base + path, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _delete(base: str, path: str):
    req = urllib.request.Request(base + path, method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _chat_once(base: str, cid: str, content: str, timeout: float = 120) -> dict:
    """POST /api/chat and read the SSE stream until run_completed/run_failed."""
    data = json.dumps({"conversation_id": cid, "content": content}, ensure_ascii=False).encode()
    req = urllib.request.Request(base + "/api/chat", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    text_parts: list[str] = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            if ev.get("type") == "text_delta":
                text_parts.append(ev.get("text", ""))
            elif ev.get("type") in ("run_completed", "run_failed"):
                return {"text": "".join(text_parts), "type": ev.get("type"),
                        "is_error": bool(ev.get("is_error"))}
    return {"text": "".join(text_parts), "type": "incomplete", "is_error": True}


def _find_fixtures(proj: Path, slug: str) -> list[tuple[Path, dict]]:
    """Every declared test fixture for the asset (all are verified, not just one).

    `test/fixtures.json` lists [{file|fixture, capability, expected}, ...]; the
    legacy single `test/expected.json` is still accepted.
    """
    test_dir = proj / "assets" / slug / "test"
    if not test_dir.exists():
        return []
    specs: list[dict] = []
    multi = test_dir / "fixtures.json"
    if multi.exists():
        data = json.loads(multi.read_text(encoding="utf-8"))
        specs = data if isinstance(data, list) else data.get("fixtures", [])
    elif (test_dir / "expected.json").exists():
        specs = [json.loads((test_dir / "expected.json").read_text(encoding="utf-8"))]
    out: list[tuple[Path, dict]] = []
    for spec in specs:
        fixture = test_dir / spec.get("fixture", spec.get("file", "fixture.png"))
        if fixture.exists():
            out.append((fixture, spec))
    return out


def _render_example_png(features: list, cfg: dict) -> bytes | None:
    """Render a grounded feature vector back to an image, using only the asset's
    declared image preprocessing (canvas / pixel scale / ink polarity)."""
    import io as _io
    import numpy as np
    from PIL import Image

    ip = cfg.get("image_preprocess") or {}
    canvas, ps = ip.get("canvas"), ip.get("pixel_scale")
    if not canvas or not ps:
        return None
    n = int(canvas[0])
    if len(features) != n * n:
        return None
    arr = np.clip(np.asarray(features, dtype=float).reshape(n, n) / float(ps), 0.0, 1.0)
    if ip.get("ink_polarity") == "ink_on_light":
        gray, bg = (255 * arr).astype("uint8"), 0
    else:
        gray, bg = (255 * (1.0 - arr)).astype("uint8"), 255
    img = Image.fromarray(gray, "L").resize((n * 24, n * 24), Image.NEAREST)
    pad = 48
    out = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), bg)
    out.paste(img, (pad, pad))
    buf = _io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def _invariance_source(proj: Path, slug: str, cfg: dict) -> tuple[bytes | None, str]:
    """An image with a known digit, independent of the adapter: a shipped test
    fixture if present, otherwise a grounded example rendered via the asset's
    declared preprocessing. No asset-specific logic."""
    test_dir = proj / "assets" / slug / "test"
    if test_dir.exists():
        for p in sorted(test_dir.glob("fixture*.png")) + sorted(test_dir.glob("fixture*.jpg")):
            return p.read_bytes(), p.name
    cap = cfg.get("default_capability")
    for rec in (cfg.get("examples") or {}).get(cap) or []:
        feats = (rec.get("args") or {}).get("features")
        if isinstance(feats, list):
            png = _render_example_png(feats, cfg)
            if png:
                return png, "rendered example"
    return None, ""


def _warp_width(png: bytes, factor: float) -> bytes:
    import io as _io
    from PIL import Image
    img = Image.open(_io.BytesIO(png))
    w, h = img.size
    out = img.resize((max(1, int(round(w * factor))), h), Image.BICUBIC)
    buf = _io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def build_verify_report(task_id: str) -> dict:
    """Boot the produced agent and collect real evidence for every check."""
    from .workspace import Workspace
    proj = Workspace(task_id).project
    report: dict = {"ok": False, "task_id": task_id, "checks": []}

    def check(name: str, ok: bool, evidence) -> None:
        report["checks"].append({"name": name, "status": "pass" if ok else "fail",
                                 "evidence": evidence})

    cfg_path = proj / "config.json"
    ui_path = proj / "agent_ui.json"
    if not cfg_path.exists():
        check("config.json", False, "missing")
        return report
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    report.update({"slug": cfg.get("slug"), "input_type": cfg.get("input_type")})
    check("config.json", True, {"slug": cfg.get("slug"), "input_type": cfg.get("input_type"),
                                "capabilities": cfg.get("capabilities")})

    ui = {}
    if ui_path.exists():
        ui = json.loads(ui_path.read_text(encoding="utf-8"))
    presets = ui.get("presets") or []
    caps = cfg.get("capabilities") or []
    ui_ok = (len(presets) == 3 and bool(ui.get("input"))
             and all(v in caps for v in ui.get("result_views", [])))
    check("agent_ui.json", ui_ok,
          {"presets": presets, "input_mode": (ui.get("input") or {}).get("mode"),
           "result_views": ui.get("result_views")})
    if not ui_ok:
        return report

    port = _free_port()
    proc = subprocess.Popen([sys.executable, "run.py", "--port", str(port)],
                            cwd=str(proj), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        booted = False
        for _ in range(40):
            try:
                _get(base, "/api/health", timeout=1)
                booted = True
                break
            except Exception:
                time.sleep(0.5)
        check("boot", booted, {"port": port})
        if not booted:
            return report

        served_cfg = _get(base, "/api/config")
        check("config_endpoint", served_cfg.get("slug") == cfg.get("slug"),
              {"slug": served_cfg.get("slug")})

        # real inference with the asset's first grounded example
        example = None
        for cap in caps:
            recs = (cfg.get("examples") or {}).get(cap) or []
            if recs and isinstance(recs[0].get("args"), dict):
                example = (cap, recs[0]["args"])
                break
        if example:
            cap, args = example
            run = _post(base, "/api/model/run", {"capability": cap, "args": args, "trace": True})
            result = run.get("result")
            usable = isinstance(result, (int, float, dict, list)) and not isinstance(result, bool)
            check("real_inference", usable,
                  {"capability": cap, "result": result, "latency_ms": (run.get("trace") or {}).get("latency_ms")})

        # input-adapter check on ALL real fixtures the asset ships
        fixtures = _find_fixtures(proj, cfg.get("slug", ""))
        if fixtures:
            results = []
            all_ok = True
            for fixture, spec in fixtures:
                up = _post_multipart(base, "/api/upload", fixture.name, fixture.read_bytes())
                feats = up.get("features")
                if feats is None and up.get("rows"):
                    feats = up["rows"][0].get("features")
                got = _post(base, "/api/model/run",
                            {"capability": spec.get("capability", cfg.get("default_capability")),
                             "args": {"features": feats}, "trace": True})
                passed = got.get("result") == spec.get("expected")
                all_ok = all_ok and passed
                results.append({"fixture": fixture.name, "expected": spec.get("expected"),
                                "actual": got.get("result"),
                                "preprocess": (up.get("trace") or {}).get("ink_polarity")})
            check("input_adapter_fixture", all_ok, results)

        # Input invariance: the same digit presented with a different aspect ratio
        # must produce (nearly) the same model input. This catches adapters whose
        # resizing distorts the digit even when a single clean fixture happens to
        # still classify — the failure mode that clean, in-distribution fixtures
        # miss. Generic for every image asset; no model-specific rules.
        if cfg.get("input_type") == "image" and cfg.get("image_preprocess"):
            src, src_name = _invariance_source(proj, cfg.get("slug", ""), cfg)
            if not src:
                check("input_invariance", False,
                      {"reason": "asset declares no test fixture or example features to render"})
            else:
                ps = float((cfg.get("image_preprocess") or {}).get("pixel_scale") or 0)
                tol = 0.05 * ps
                ref = (_post_multipart(base, "/api/upload", "ref.png", src) or {}).get("features")
                warps: dict = {}
                inv_ok = bool(ref)
                for factor in (0.8, 1.2):
                    feats = (_post_multipart(base, "/api/upload",
                                             f"warp_{factor}.png", _warp_width(src, factor)) or {}).get("features")
                    if not feats or len(feats) != len(ref):
                        inv_ok = False
                        warps[str(factor)] = {"error": "no comparable features"}
                        continue
                    diffs = [abs(a - b) for a, b in zip(feats, ref)]
                    mean_diff = sum(diffs) / len(diffs)
                    good = mean_diff <= tol
                    inv_ok = inv_ok and good
                    warps[str(factor)] = {"mean_diff": round(mean_diff, 3),
                                          "max_diff": round(max(diffs), 3),
                                          "tolerance": round(tol, 3)}
                check("input_invariance", inv_ok,
                      {"source": src_name, "pixel_scale": ps, "aspect_warps": warps})
        elif cfg.get("input_type") == "tabular" and cfg.get("feature_names"):
            # Column order must not matter: the adapter maps by declared names.
            names = list(cfg["feature_names"])
            cap = cfg.get("default_capability")
            feats = None
            for rec in (cfg.get("examples") or {}).get(cap) or []:
                f = (rec.get("args") or {}).get("features")
                if isinstance(f, list) and len(f) == len(names):
                    feats = f
                    break
            if feats is None:
                check("input_invariance", False,
                      {"reason": "no declared example features to build a CSV probe"})
            else:
                header = ",".join(reversed(names))
                row = ",".join(str(v) for v in reversed(feats))
                up = _post_multipart(base, "/api/upload", "probe.csv",
                                     (header + "\n" + row + "\n").encode())
                got = ((up or {}).get("rows") or [{}])[0].get("features") or []
                diff = max((abs(a - b) for a, b in zip(got, feats)), default=float("inf"))
                check("input_invariance", len(got) == len(feats) and diff <= 1e-6,
                      {"probe": "reversed CSV column order", "max_diff": diff})

        # conversations CRUD roundtrip
        created = _post(base, "/api/conversations", {"title": "verify"})
        cid = created.get("id")
        listed = _get(base, "/api/conversations")
        cleared = _post(base, f"/api/conversations/{cid}/clear", {})
        deleted = _delete(base, f"/api/conversations/{cid}")
        check("conversations_crud",
              bool(cid) and any(c["id"] == cid for c in listed.get("conversations", []))
              and cleared.get("ok") and deleted.get("ok"),
              {"created": cid, "listed": len(listed.get("conversations", []))})

        # api docs
        docs = _get(base, "/api/apidocs")
        check("apidocs", bool(docs.get("endpoints")), {"endpoints": len(docs.get("endpoints", []))})

        # one real chat turn (requires LLM credentials; report honestly if absent)
        import os
        has_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))
        if has_key:
            c2 = _post(base, "/api/conversations", {"title": "verify-chat"})
            chat = _chat_once(base, c2.get("id"), presets[0])
            check("chat_roundtrip", bool(chat.get("text", "").strip()) and not chat.get("is_error"),
                  {"type": chat.get("type"), "text_len": len(chat.get("text", ""))})
            _delete(base, f"/api/conversations/{c2.get('id')}")
        else:
            check("chat_roundtrip", False, "skipped: no LLM credentials in this environment")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    report["ok"] = all(c["status"] == "pass" for c in report["checks"]
                       if not (c["name"] == "chat_roundtrip" and "skipped" in str(c["evidence"])))
    (proj / ".m2a_verify.json").write_text(
        json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return report


def cmd_verify(args) -> int:
    report = build_verify_report(args.task_id)
    print(json.dumps(report, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("task_id")
    g.add_argument("asset_dir")
    g.set_defaults(fn=cmd_generate)
    sc = sub.add_parser("selfcheck")
    sc.add_argument("task_id")
    sc.set_defaults(fn=cmd_selfcheck)
    v = sub.add_parser("verify")
    v.add_argument("task_id")
    v.set_defaults(fn=cmd_verify)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
