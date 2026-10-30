"""Model2Agent V1.0 — Gradio UI (three-column AI Native workbench).

Left  : task history (persisted)
Center: real streaming Claude Agent SDK chat (tool cards, stop)
Right : workspace file explorer + code preview + preview controls

All agent work is driven by claude_agent_sdk (m2a_app/agent.py). No OpenAI
fallback, no hand-written agent loop, no faked tool events.
"""
from __future__ import annotations
import html as _html
import time
from pathlib import Path

import gradio as gr

from m2a_app import config
from m2a_app.devices import detect_devices, device_available
from m2a_app.store import Store
from m2a_app.workspace import Workspace
from m2a_app.agent import SESSIONS
from m2a_app.preview import PreviewManager

config.ensure_dirs()
store = Store()
previews = PreviewManager()

ACCENT = "#14b8a6"
CSS = """
:root{--accent:__ACCENT__;--bg:#f7f8fa;--panel:#ffffff;--border:#e5e7eb;--text:#1f2937;--muted:#6b7280}
*{font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif}
body{background:var(--bg);color:var(--text)}
.m2a-wrap{height:100vh;display:flex;overflow:hidden}
.m2a-side{width:240px;min-width:240px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column}
.m2a-center{flex:1;display:flex;flex-direction:column;min-width:0;background:var(--bg)}
.m2a-right{width:400px;min-width:400px;background:var(--panel);border-left:1px solid var(--border);display:flex;flex-direction:column}
.m2a-brand{padding:16px;font-weight:700;font-size:16px;border-bottom:1px solid var(--border);color:var(--accent)}
.m2a-hist{flex:1;overflow:auto;padding:8px}
.m2a-task{padding:10px 12px;border-radius:10px;margin-bottom:6px;cursor:pointer;border:1px solid transparent}
.m2a-task:hover{background:var(--bg)}
.m2a-task.active{background:#e6f7f4;border-color:var(--accent)}
.m2a-task .t{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.m2a-task .s{font-size:11px;color:var(--muted);margin-top:2px}
.m2a-topbar{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;background:var(--panel)}
.m2a-chat{flex:1;overflow:auto;background:var(--bg)}
.m2a-inputbar{padding:12px 16px;border-top:1px solid var(--border);background:var(--panel);display:flex;gap:8px}
.m2a-btn{background:var(--accent);color:#fff;border:none;border-radius:10px;padding:0 16px;font-weight:600;cursor:pointer}
.m2a-btn.ghost{background:#eef2f4;color:var(--text)}
.m2a-right-head{padding:12px 16px;border-bottom:1px solid var(--border);font-weight:600;display:flex;justify-content:space-between;align-items:center}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;background:#e6f7f4;color:var(--accent);font-weight:600}
.dim{color:var(--muted)}
.empty{padding:40px 20px;text-align:center;color:var(--muted)}
.modal{background:#fff;border-radius:16px;padding:24px;margin:48px auto 0;width:480px;max-width:92vw;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.backdrop{position:fixed;inset:0;background:rgba(0,0,0,.25);z-index:100}
.m2a-card{border:1px solid var(--border);border-radius:10px;margin-top:8px;overflow:hidden;font-size:13px;background:#fff}
.m2a-card-head{padding:8px 12px;background:#f3f4f6;font-weight:600}
.m2a-card-res{padding:8px 12px;white-space:pre-wrap;color:var(--muted);max-height:180px;overflow:auto}
.m2a-spin{display:inline-block;width:10px;height:10px;border:2px solid var(--accent);border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
""" .replace("__ACCENT__", ACCENT)


def fmt_time(ts):
    return time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else ""


def history_html(active=""):
    tasks = store.list_tasks()
    if not tasks:
        return '<div class="empty">还没有任务<br>点击「新建任务」开始</div>'
    return "".join(
        f'<div class="m2a-task {"active" if t["task_id"]==active else ""}" '
        f'style="display:flex;justify-content:space-between;align-items:center">'
        f'<div style="min-width:0"><div class="t">{_html.escape(t["name"])}</div>'
        f'<div class="s">{fmt_time(t.get("updated_at",0))}</div></div>'
        f'<span class="dim" style="font-size:11px">{_html.escape(t.get("status",""))}</span></div>'
        for t in store.list_tasks())


_chat_histories: dict[str, list] = {}


def _render_agent(full_text, tools):
    parts = [_html.escape(full_text)]
    for c in tools:
        if c["status"] == "running":
            head = f'<span class="m2a-spin"></span> {_html.escape(c["name"])} · 执行中'
        else:
            head = f'✅ {_html.escape(c["name"])} · 完成'
        inp = f'<div class="m2a-card-res" style="color:#4b5563">{_html.escape(c.get("input",""))[:200]}</div>' if c.get("input") else ""
        res = f'<div class="m2a-card-res">{_html.escape(c.get("result",""))[:2000]}</div>' if c.get("result") else ""
        parts.append(f'<div class="m2a-card"><div class="m2a-card-head">{head}</div>{inp}{res}</div>')
    return "".join(parts)


def _chat_value(task_id):
    out = []
    for m in _chat_histories.get(task_id, []):
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        else:
            out.append({"role": "assistant", "content": _render_agent(m.get("full", ""), m.get("tools", []))})
    return out


# ---------------- handlers ----------------
def _gate_device():
    if not store.get_device():
        return gr.update(visible=True), gr.update(visible=False)
    return gr.update(visible=False), gr.update(visible=True)


def device_choices():
    return [(d.label, d.id) for d in detect_devices()]


def save_device(selected_id):
    if not selected_id:
        return gr.update(visible=True), "请选择设备"
    if not device_available(selected_id):
        return gr.update(visible=True), "设备不可用，请重新选择"
    store.set_device(selected_id)
    return gr.update(visible=False), ""


def create_task(name, goal, files):
    if not name or not goal:
        return None, "", "请填写任务名称和任务目标"
    if not files:
        return None, "", "请上传模型资产（ZIP 或目录）"
    task = store.create_task(name, goal, [])
    ws = Workspace(task["task_id"]).create()
    asset_names = []
    flist = files if isinstance(files, list) else [files]
    for f in flist:
        fpath = getattr(f, "name", f)
        try:
            if str(fpath).lower().endswith(".zip"):
                ws.add_asset_zip(fpath)
            else:
                ws.add_asset(fpath)
            asset_names.append(Path(str(fpath)).name)
        except Exception as e:
            store.update_task(task["task_id"], status="error")
            return None, "", f"资产处理失败: {e}"
    store.update_task(task["task_id"], assets=asset_names, status="ready")
    first = (f"【新任务：{name}】\n目标：{goal}\n已上传资产：{', '.join(asset_names)}\n"
             f"工作空间：{ws.root}\n当前设备：{store.get_device()}\n"
             f"请先用 model-inspection 技能分析模型资产，再推进生成。")
    _chat_histories[task["task_id"]] = []
    return task["task_id"], first, ""


async def stream_agent(task_id, new_msg, history):
    if not task_id:
        return
    if task_id not in _chat_histories:
        _chat_histories[task_id] = []
    if new_msg:
        _chat_histories[task_id].append({"role": "user", "content": new_msg})
    holder = {"role": "assistant", "full": "", "tools": []}
    _chat_histories[task_id].append(holder)
    yield _chat_value(task_id)

    ws = Workspace(task_id)
    if not SESSIONS.has(task_id):
        first_prompt = new_msg
    else:
        first_prompt = None
    sess = await SESSIONS.get_or_create(task_id, ws.root, first_prompt=first_prompt)
    prompt = first_prompt if first_prompt else new_msg

    full = ""
    async for ev in sess.respond(prompt):
        if ev["type"] == "text":
            full += ev["text"]
            holder["full"] = full
            yield _chat_value(task_id)
        elif ev["type"] == "tool":
            cid = ev.get("card_id")
            card = next((c for c in holder["tools"] if c.get("card_id") == cid), None)
            if card is None:
                holder["tools"].append({"card_id": cid, "name": ev["name"], "status": ev["status"],
                                        "input": ev.get("input", ""), "result": ev.get("result", "")})
            else:
                card["status"] = ev["status"]
                card["result"] = ev.get("result", "")
            yield _chat_value(task_id)
        elif ev["type"] == "result":
            store.update_task(task_id, status="done")
            yield _chat_value(task_id)


async def stop_agent(task_id):
    if task_id:
        await SESSIONS.interrupt(task_id)
    return "已发送停止信号"


def _sel_path(selection):
    if not selection:
        return ""
    item = selection[0] if isinstance(selection, list) else selection
    return getattr(item, "name", item) if not isinstance(item, str) else item


def preview_file(task_id, selection):
    path = _sel_path(selection)
    if not task_id or not path:
        return gr.update(value="// 选择文件查看", language="python")
    ws = Workspace(task_id)
    try:
        p = Path(path)
        # FileExplorer returns absolute paths; make relative to workspace
        try:
            rel = p.relative_to(ws.root)
        except ValueError:
            rel = p
        if not p.is_file():
            return gr.update(value="(目录)", language="markdown")
        text = p.read_text(encoding="utf-8", errors="replace")
        if str(rel).endswith(".py"):
            lang = "python"
        elif str(rel).endswith(".json"):
            lang = "json"
        elif str(rel).endswith((".md", ".txt")):
            lang = "markdown"
        else:
            lang = "text"
        return gr.update(value=text[:20000], language=lang)
    except Exception as e:
        return gr.update(value=f"// 无法读取: {e}", language="text")


def set_workspace_root(task_id):
    ws = Workspace(task_id)
    return gr.update(root=str(ws.root))


def start_preview(task_id):
    ws = Workspace(task_id)
    entry = ws.project / "run.py"
    if not entry.exists():
        return gr.update(value=f'<div class="empty">未找到 {entry.name}，先生成项目</div>')
    st = previews.start(task_id, str(entry))
    if st.status == "running":
        return gr.update(value=f'<iframe src="{st.url}" style="width:100%;height:70vh;border:none;border-radius:10px"></iframe>')
    return gr.update(value=f'<div class="empty">启动失败：{_html.escape(st.error)}</div>')


def stop_preview(task_id):
    previews.stop(task_id)
    return gr.update(value='<div class="empty">预览已停止</div>')


def download_zip(task_id):
    if not task_id:
        return None
    ws = Workspace(task_id)
    out = config.DATA_DIR / f"{task_id}.zip"
    return ws.export_zip(out)


def status_badge(task_id):
    t = store.get_task(task_id)
    if not t:
        return "未选择任务"
    return (f'<span class="badge">{_html.escape(t.get("status",""))}</span> '
            f'设备：{store.get_device()} 任务：{task_id}')


def select_task(task_id):
    """Restore a task's history, workspace root, status."""
    return _chat_value(task_id), gr.update(root_dir=str(Workspace(task_id).root)), status_badge(task_id), history_html(task_id)


# ---------------- layout ----------------
with gr.Blocks(title="Model2Agent") as demo:
    task_state = gr.State("")
    # LEFT
    with gr.Column(scale=0, elem_classes="m2a-side"):
        gr.HTML('<div class="m2a-brand">Model2Agent</div>')
        new_btn = gr.Button("+ 新建任务", elem_classes="m2a-btn", size="sm")
        hist = gr.HTML(history_html(""), elem_classes="m2a-hist")

    # CENTER
    with gr.Column(scale=1, elem_classes="m2a-center"):
        with gr.Row(elem_classes="m2a-topbar"):
            gr.HTML("<div style='font-weight:600'>主 Agent 工作台</div>")
            status_html = gr.HTML(status_badge(""))
            stop_btn = gr.Button("停止", elem_classes="m2a-btn ghost", size="sm")
        chat = gr.Chatbot(height="72vh", show_label=False, elem_classes="m2a-chat", sanitize_html=False)
        with gr.Row(elem_classes="m2a-inputbar"):
            msg = gr.Textbox(placeholder="用自然语言描述下一步，或追问…", lines=2, scale=1, show_label=False, container=False)
            send = gr.Button("发送", elem_classes="m2a-btn")

    # RIGHT
    with gr.Column(scale=0, elem_classes="m2a-right"):
        with gr.Row(elem_classes="m2a-right-head"):
            gr.HTML("工作空间")
            prev_btn = gr.Button("启动预览", elem_classes="m2a-btn ghost", size="sm")
            stop_prev = gr.Button("停止预览", elem_classes="m2a-btn ghost", size="sm")
            dl_btn = gr.Button("下载 ZIP", elem_classes="m2a-btn ghost", size="sm")
        with gr.Tabs():
            with gr.Tab("文件"):
                fe = gr.FileExplorer(root_dir=str(config.WORKSPACES_DIR), scale=1, height=420)
                prev = gr.Code(value="// 选择文件查看", language="python", interactive=False, lines=16)
            with gr.Tab("预览"):
                preview_frame = gr.HTML('<div class="empty">预览未启动</div>')

    # DEVICE MODAL
    with gr.Column(visible=False) as dev_panel:
        gr.HTML('<div class="backdrop"></div>')
        with gr.Row(scale=0):
            with gr.Column(scale=1):
                gr.HTML('<div class="modal"><div style="font-size:18px;font-weight:700;margin-bottom:6px">设备配置</div>'
                        '<div class="dim" style="margin-bottom:14px">请选择本机真实可用的计算设备（仅一次，可随时修改）</div>')
                dev_radio = gr.Radio(choices=device_choices(), label="计算设备", value=None)
                dev_err = gr.HTML('<span style="color:#dc2626;font-size:13px"></span>')
                with gr.Row():
                    save_dev = gr.Button("保存设备", elem_classes="m2a-btn")
                    cancel_dev = gr.Button("取消", elem_classes="m2a-btn ghost")

    # NEW TASK FORM
    with gr.Column(visible=False) as new_panel:
        gr.HTML('<div class="backdrop"></div>')
        with gr.Row(scale=0):
            with gr.Column(scale=1):
                gr.HTML('<div class="modal"><div style="font-size:18px;font-weight:700;margin-bottom:14px">新建模型 Agent 任务</div>')
                name_in = gr.Textbox(label="任务名称", placeholder="例如：植物病害识别 Agent")
                goal_in = gr.Textbox(label="任务目标", lines=4, placeholder="用自然语言描述要生成什么 Agent…")
                files_in = gr.File(label="模型资产（ZIP 或目录，可多文件）", file_count="multiple")
                form_err = gr.HTML('<span style="color:#dc2626;font-size:13px"></span>')
                with gr.Row():
                    create_btn = gr.Button("创建任务并开始", elem_classes="m2a-btn")
                    cancel_form = gr.Button("取消", elem_classes="m2a-btn ghost")

    # ---- wiring ----
    new_btn.click(_gate_device, None, [dev_panel, new_panel])
    save_dev.click(save_device, [dev_radio], [dev_panel, dev_err]).then(
        lambda: (gr.update(visible=True), history_html("")), None, [new_panel, hist])
    cancel_dev.click(lambda: gr.update(visible=False), None, [dev_panel])
    cancel_form.click(lambda: gr.update(visible=False), None, [new_panel])

    # create: set task_state + first prompt; on error show message, panel stays
    create_btn.click(create_task, [name_in, goal_in, files_in], [task_state, msg, form_err]).then(
        lambda tid, first: (
            gr.update(visible=bool(tid)),
            history_html(tid) if tid else gr.update(),
            status_badge(tid) if tid else gr.update(),
            gr.update(root_dir=str(Workspace(tid).root)) if tid else gr.update(),
            tid if tid else gr.update(),
        ),
        [task_state, form_err], [new_panel, hist, status_html, fe, task_state]).then(
        lambda tid, first: _chat_value(tid) if tid else gr.update(), [task_state, msg], [chat]).then(
        stream_agent, [task_state, msg, chat], [chat])

    # send a follow-up message (continues the session)
    send.click(stream_agent, [task_state, msg, chat], [chat]).then(
        lambda: gr.update(value=""), None, [msg])

    stop_btn.click(stop_agent, [task_state], [status_html])
    fe.select(preview_file, [task_state, fe], [prev])
    prev_btn.click(start_preview, [task_state], [preview_frame])
    stop_prev.click(stop_preview, [task_state], [preview_frame])
    dl_btn.click(download_zip, [task_state], [gr.File(label="下载", visible=False)])

    # task history click -> restore. Gradio HTML can't dispatch; we wire a hidden
    # textbox that JS fills on .m2a-task click. Use a State + .change via JS is not
    # trivial; instead expose a small JS that sets a hidden Textbox and clicks a
    # button. We add a hidden task picker fed by demo.load JS.
    picker = gr.Textbox(visible=False)
    pick_btn = gr.Button(visible=False)
    demo.load(
        lambda: gr.update(value=""),
        None, [picker]
    )
    pick_btn.click(select_task, [picker], [chat, fe, status_html, hist])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(__import__("os").getenv("M2A_PORT","7861")), inbrowser=False, css=CSS)
