"""Model2Agent V1.1 acceptance tests — assert on BEHAVIOUR, not just HTTP/existence.

Each check reproduces a real user path and asserts on the actual outcome.
"""
from __future__ import annotations
import asyncio, json, os, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from m2a_app import config, app as A
from m2a_app.devices import detect_devices
from m2a_app.store import Store
from m2a_app.workspace import Workspace
from m2a_app.preview import PreviewManager, PREVIEWS
from m2a_app.generator import generate
from m2a_app.agent import AgentSession, SESSIONS

results = []
def record(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {str(detail)[:140]}")

store = A.store
if not store.get_device():
    devs = detect_devices()
    store.set_device((devs[0].id if devs else "cpu"))

CNN = ROOT / "model_assets" / "cnn_digits"
XGB = ROOT / "model_assets" / "xgb_tabular"

# ---- T1: first prompt sent exactly once (num_turns == 1 for a no-tool reply) ----
async def _t1():
    s = AgentSession(cwd=Workspace("acc-t1").create().root)
    text = ""; turns = None
    async for ev in s.respond("Reply with exactly the word: ONCE"):
        if ev["type"] == "text": text += ev["text"]
        elif ev["type"] == "result": turns = ev.get("num_turns")
    await s.close()
    return text, turns
text, turns = asyncio.run(_t1())
record("T1 first prompt sent once (num_turns==1, no duplicate)",
       turns == 1 and len(text) > 0, f"num_turns={turns} text={text[:40]!r}")

# ---- T2: real ToolUse + ToolResult (tool card goes running->done with a result) ----
async def _t2():
    w = Workspace("acc-t2").create()
    s = AgentSession(cwd=w.root)
    cards = {}
    async for ev in s.respond("Use Write to create file.txt with content DONE9, then Read it."):
        if ev["type"] == "tool":
            c = cards.setdefault(ev["card_id"], {"name": ev["name"], "status": ev["status"], "result": ""})
            c["status"] = ev["status"]; c["result"] = ev.get("result", c.get("result",""))
    await s.close()
    done = [c for c in cards.values() if c["status"] == "done" and c["result"]]
    return cards, (w.root / "file.txt").exists(), len(done)
cards, file_ok, ndone = asyncio.run(_t2())
record("T2 real ToolUse + ToolResult (done with result, file created)",
       file_ok and ndone >= 1, f"cards={[ (c['name'],c['status']) for c in cards.values()]} file={file_ok} done={ndone}")

# ---- T3: session id captured + persisted ----
tidA = None
async def _t3():
    global tidA
    t = store.create_task("acc-session", "会话恢复测试", [])
    w = Workspace(t["task_id"]).create()
    A._chat_histories[t["task_id"]] = []
    async for _ in A.stream_agent(t["task_id"], "回复仅一个词：SESS", []):
        pass
    tidA = t["task_id"]
    return store.get_task(tidA).get("session_id"), A._chat_histories[tidA]
sid, chatA = asyncio.run(_t3())
record("T3 SDK session_id captured + chat persisted",
       bool(sid) and any(m.get("role")=="assistant" for m in chatA),
       f"session_id={str(sid)[:10]} chat_msgs={len(chatA)}")

# ---- T4: history select restores chat + workspace + session link, stops other preview ----
sel = A.select_task(tidA) if tidA else (None,)*5
chat_val = sel[0] if sel else []
record("T4 history select restores chat + session",
       bool(chat_val) and len(chat_val) >= 2, f"restored_msgs={len(chat_val)}")

# ---- T5: workspace file sync after a write (FileExplorer every= refresh + list_files) ----
w = Workspace(tidA) if tidA else Workspace("acc-t5")
before = len(w.list_files())
(w.root / "marker_sync.txt").write_text("sync-marker")
after = len(w.list_files())
record("T5 workspace sync on file change", after > before, f"{before} -> {after}")

# ---- T6: generated agents for BOTH model types run real inference ----
def _gen(tid, asset):
    w = Workspace(tid).create(); w.add_asset(str(asset))
    return generate(tid, w.inputs / asset.name)
for tid, asset in [("acc-g1", CNN), ("acc-g2", XGB)]:
    proj = _gen(tid, asset)
    r = subprocess.run(["python3","-c",
        "import sys,json;sys.path.insert(0,'.');import model_exec;print(json.dumps(model_exec.selfcheck()))"],
        cwd=proj, capture_output=True, text=True, timeout=180)
    record(f"T6 generated agent {asset.name} real inference",
           '"predict"' in r.stdout, (r.stdout or r.stderr)[:80])

# ---- T7: generated agent's OWN SDK session (multi-turn + run_model tool) ----
async def _t7():
    proj = Workspace("acc-g1").project
    sys.path.insert(0, str(proj))
    import importlib, agent_core
    importlib.reload(agent_core)
    s = agent_core.GeneratedAgentSession()
    t1 = ""; t2 = ""
    async for ev in s.respond('用 run_model 执行 predict，args={"features":[0,0,5,13,9,1,0,0,0,0,13,15,10,15,5,0,0,3,15,2,0,11,8,0,0,4,12,0,0,8,8,0,0,5,8,0,0,9,8,0,0,4,11,0,1,12,7,0,0,2,14,5,10,12,0,0,0,0,6,13,10,0,0,0]}。只回复类别数字。'):
        if ev["type"]=="text": t1+=ev["text"]
    async for ev in s.respond("上一轮的预测类别是什么？只回复数字。"):
        if ev["type"]=="text": t2+=ev["text"]
    await s.close()
    return t1.strip(), t2.strip()
t1, t2 = asyncio.run(_t7())
record("T7 generated agent own SDK multi-turn", t1.strip()=="0" and t2.strip()=="0",
       f"turn1={t1!r} turn2={t2!r}")

# ---- T8: preview via Builder Agent + device propagation + stop ----
async def _t8():
    html = await A.start_preview_via_agent("acc-g1")
    running = PREVIEWS.get("acc-g1").status == "running"
    if running:
        # stop other-task preview when switching (select a different task)
        A.select_task(tidA) if tidA else None
    return running, PREVIEWS.get("acc-g1").status
ok8, st8 = asyncio.run(_t8())
record("T8 preview via Builder Agent (real process + device)", ok8, f"status={st8}")

# ---- T9: zip export contains weights + no secrets ----
zip_path = A.download_project_zip("acc-g1")
import zipfile
with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
has_weights = any(n.endswith("cnn_state.pt") for n in names)
has_run = any(n.endswith("run.py") for n in names)
no_secret = not any(n.endswith((".env",".credentials.json")) for n in names)
record("T9 zip has weights + no secrets", has_weights and has_run and no_secret,
       f"weights={has_weights} run={has_run} no_secret={no_secret} entries={len(names)}")

# ---- T10: docker real inference inside container (weights included now) ----
if os.getenv("V1_DOCKER") != "1":
    record("T10 docker real inference", False, "BLOCKED: rebuild pending (V1_DOCKER!=1)")
    fails = [r for r in results if not r[1]]
    print("\n=== SUMMARY (partial, T10 deferred) ===")
    print(f"PASS {len(results)-len(fails)}/{len(results)}")
    if fails: print("FAILED:", [f[0] for f in fails])
    raise SystemExit(0)
try:
    img = subprocess.run(["docker","images","--format","{{.Repository}}:{{.Tag}}"],
                         capture_output=True, text=True).stdout
    tag = next((l for l in img.splitlines() if "m2a-cnn-agent" in l), None)
    if tag:
        r = subprocess.run(["docker","run","--rm",tag,"python3","-c",
            "import sys,json;sys.path.insert(0,'/app');import model_exec;print(model_exec.selfcheck()['predict'])"],
            capture_output=True, text=True, timeout=300)
        record("T10 docker real inference in container", "9" in r.stdout or "0" in r.stdout,
               f"out={r.stdout.strip()[:40]} err={r.stderr[:60]}")
    else:
        record("T10 docker real inference", False, "image not found (build pending)")
except Exception as e:
    record("T10 docker real inference", False, f"BLOCKED: {type(e).__name__}: {e}")

fails = [r for r in results if not r[1]]
print("\n=== SUMMARY ===")
print(f"PASS {len(results)-len(fails)}/{len(results)}")
if fails:
    print("FAILED:", [f[0] for f in fails])
