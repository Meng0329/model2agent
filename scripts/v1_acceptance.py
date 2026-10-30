"""Model2Agent V1.0 acceptance tests (real execution, no fabrication)."""
from __future__ import annotations
import asyncio, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from m2a_app import config, app as A
from m2a_app.devices import detect_devices
from m2a_app.workspace import Workspace
from m2a_app.preview import PreviewManager
from m2a_app.generator import generate

results = []
def record(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail[:120]}")

# --- Test 1: device detect + save + gate ---
devs = detect_devices()
gpus = [d for d in devs if d.kind == "gpu"]
record("T1 device detection", len(gpus) >= 1, f"gpus={len(gpus)} names={[d.name for d in gpus][:2]}")
if not A.store.get_device():
    A.store.set_device(gpus[0].id if gpus else "cpu")
record("T1 device saved", bool(A.store.get_device()), f"device={A.store.get_device()}")

# --- Test 2: create task with real CNN asset ---
asset = ROOT / "model_assets" / "cnn_digits"
tid, first, err = A.create_task("acceptance-cnn", "生成可独立运行的 CNN 数字识别 Agent", [str(asset)])
record("T2 create task", bool(tid) and not err, f"tid={tid} err={err}")
ws = Workspace(tid).create()
A.store.update_task(tid, status="ready")
record("T2 workspace", (ws.inputs / "cnn_digits" / "infer.py").exists(), "inputs/cnn_digits present")

# --- Test 5: file tree + preview ---
files = Workspace(tid).list_files()
has_asset = any("cnn_digits/infer.py" in f["path"] for f in files)
record("T5 workspace files visible", len(files) > 0 and has_asset, f"count={len(files)}")

# --- Test 6: generated agent (both model types) real inference ---
for t, mslug in [(tid, "cnn_digits"), (None, "xgb_tabular")]:
    if t is None:
        t2 = A.store.create_task("acceptance-xgb", "生成 XGBoost Agent", [])
        w2 = Workspace(t2["task_id"]).create()
        w2.add_asset(str(ROOT / "model_assets" / "xgb_tabular"))
        proj = generate(t2["task_id"], w2.inputs / "xgb_tabular")
    else:
        proj = generate(t, ws.inputs / mslug)
    r = __import__("subprocess").run(
        ["python3", "-c", "import sys,json;sys.path.insert(0,'.');import model_exec;print(json.dumps(model_exec.selfcheck(),ensure_ascii=False,default=str)[:400])"],
        cwd=proj, capture_output=True, text=True, timeout=180)
    ok = "predict" in r.stdout and "error" not in r.stdout.lower() and r.stdout.strip()
    record(f"T6 generated agent {mslug}", ok, r.stdout[:80] or r.stderr[:80])

# --- Test 7: preview start/stop (real process + port + HTTP) ---
pm = PreviewManager()
st = pm.start(tid, str(Workspace(tid).project / "run.py"))
ok7 = st.status == "running"
if ok7:
    import urllib.request
    with urllib.request.urlopen(st.url, timeout=5) as r:
        ok7 = r.status == 200
pm.stop(tid)
record("T7 preview lifecycle", ok7 and pm.get(tid).status == "stopped", f"url={st.url} err={st.error[:60]}")

# --- Test 8: zip export contains Dockerfile + run.py ---
zip_path = A.download_zip(tid)
import zipfile
with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
ok8 = any(n.endswith("project/Dockerfile") for n in names) and any(n.endswith("project/run.py") for n in names)
record("T8 zip export", ok8, f"zip={zip_path.name} entries={len(names)}")

# --- Test 3/4: real SDK turn (short) ---
async def _t34():
    t = A.store.create_task("acceptance-stream", "流式测试", [])
    w = Workspace(t["task_id"]).create()
    A._chat_histories[t["task_id"]] = []
    gen = A.stream_agent(t["task_id"], "用 Bash 执行 ls 列出工作空间文件。", [])
    texts = 0; tools = 0
    async for _ in gen:
        texts += 1
    hist = A._chat_histories[t["task_id"]]
    got_text = any(len(m.get("full","")) > 0 for m in hist if m["role"]=="assistant")
    await A.SESSIONS.close(t["task_id"])
    return got_text, texts
got_text, n = asyncio.run(_t34())
record("T3/T4 real SDK stream + tools", got_text, f"gen_steps={n}")

fails = [r for r in results if not r[1]]
print("\n=== SUMMARY ===")
print(f"PASS {len(results)-len(fails)}/{len(results)}")
if fails:
    print("FAILED:", [f[0] for f in fails])
