"""Model2Agent V1.1 — Gradio UI (three-column AI Native workbench).

Left  : clickable task history (persisted) + restore on select
Center: real streaming Claude Agent SDK chat (tool cards, stop)
Right : workspace FileExplorer (live sync) + code preview + Agent-driven preview

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
from m2a_app.preview import PREVIEWS

config.ensure_dirs()
store = Store()

ACCENT = "#14b8a6"
CSS = """
:root{--accent:#00a3a6;--bg:#f8fafc;--panel:#fff;--border:#e5e7eb;--text:#1e293b;--muted:#64748b}
*{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif}
body{background:var(--bg);color:var(--text);margin:0}
.gradio-container{max-width:none!important;padding:0!important}
.m2a-wrap{height:100vh!important}
.m2a-side{background:var(--panel);border-right:1px solid var(--border);height:100%;overflow:auto}
.m2a-center{background:var(--bg);height:100%;display:flex;flex-direction:column;padding:0!important}
.m2a-right{background:var(--panel);border-left:1px solid var(--border);height:100%;overflow:auto}
.m2a-brand{padding:18px 16px;font-weight:700;font-size:16px;border-bottom:1px solid var(--border);color:var(--accent);letter-spacing:.2px}
.m2a-topbar{padding:10px 16px;border-bottom:1px solid var(--border);align-items:center;gap:12px;background:var(--panel)}
.m2a-topbar>*{flex:0 0 auto!important}
.m2a-status{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:420px}
.m2a-status .html-container{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.m2a-inputbar{padding:12px 16px;border-top:1px solid var(--border);background:var(--panel);gap:10px}
.m2a-btn{background:var(--accent)!important;color:#fff!important;border:none!important;border-radius:0.625rem!important;font-weight:600!important;transition:all .15s ease}
.m2a-btn:hover{filter:brightness(.95);transform:translateY(-1px)}
.m2a-btn.ghost{background:#f1f5f9!important;color:var(--text)!important;border:1px solid var(--border)!important}
.m2a-btn.ghost:hover{background:#e2e8f0!important}
.m2a-right-head{padding:12px 16px;border-bottom:1px solid var(--border);font-weight:600}
.badge{font-size:11px;padding:3px 10px;border-radius:9999px;background:#ccfbf1;color:#0f766e;font-weight:600}
.dim{color:var(--muted)}
.empty{padding:44px 20px;text-align:center;color:var(--muted)}
.m2a-overlay{position:fixed;inset:0;z-index:100;background:rgba(15,23,42,.35);display:flex;align-items:flex-start;justify-content:center;animation:fade .18s ease}
.m2a-modalbox{margin-top:56px;width:500px;max-width:92vw;background:#fff;border-radius:0.875rem;padding:26px;box-shadow:0 24px 64px rgba(15,23,42,.18);animation:pop .18s ease}
.m2a-card{border:1px solid var(--border);border-radius:0.75rem;margin-top:8px;overflow:hidden;font-size:13px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.m2a-card-head{padding:9px 12px;background:#f8fafc;font-weight:600;border-bottom:1px solid var(--border)}
.m2a-card-res{padding:9px 12px;white-space:pre-wrap;color:var(--muted);max-height:180px;overflow:auto}
.m2a-spin{display:inline-block;width:11px;height:11px;border:2px solid var(--accent);border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{from{opacity:0;transform:scale(.96) translateY(6px)}to{opacity:1;transform:scale(1) translateY(0)}}
#taskhist label{border:1px solid var(--border);border-radius:0.625rem;padding:11px 13px;margin-bottom:7px;cursor:pointer;transition:all .15s ease;background:#fff}
#taskhist label:hover{background:#f8fafc;border-color:#cbd5e1}
#taskhist label:has(input:checked){background:#ccfbf1;border-color:var(--accent)}
/* neutralize Gradio's flex-grow stretching inside the workbench columns */
.m2a-side{display:block!important}
.m2a-side .m2a-hist{max-height:calc(100vh - 240px);overflow:auto;padding-bottom:18px}
.m2a-side button{height:38px!important;min-height:38px!important;max-height:38px!important}
.m2a-right{display:block!important}
.m2a-right .tabs{max-height:calc(100vh - 120px);overflow:auto}
.m2a-center .m2a-chat{flex:1 1 auto!important;min-height:0}
"""


def fmt_time(ts):
    return time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else ""


def history_choices(active: str = ""):
    tasks = store.list_tasks()
    if not tasks:
        return []
    return [(f"{t['name']}  ·  {fmt_time(t.get('updated_at',0))}", t["task_id"]) for t in tasks]


_chat_histories: dict[str, list] = {}


def _render_agent(full_text, tools):
    parts = [_html.escape(full_text)]
    for c in tools:
        head = (f'<span class="m2a-spin"></span> {_html.escape(c["name"])} · 执行中'
                if c["status"] == "running" else f'✅ {_html.escape(c["name"])} · 完成')
        inp = (f'<div class="m2a-card-res" style="color:#4b5563">{_html.escape(c.get("input",""))[:200]}</div>'
               if c.get("input") else "")
        res = (f'<div class="m2a-card-res">{_html.escape(c.get("result",""))[:2000]}</div>' if c.get("result") else "")
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


def _persist_chat(task_id):
    Workspace(task_id).save_chat(_chat_histories.get(task_id, []))


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
    ws.save_chat([])
    return task["task_id"], first, ""


async def stream_agent(task_id, new_msg, history):
    """Real streaming agent turn. Sends the prompt EXACTLY once; persists chat+session."""
    if not task_id:
        return
    if task_id not in _chat_histories:
        _chat_histories[task_id] = Workspace(task_id).load_chat()
    if new_msg:
        _chat_histories[task_id].append({"role": "user", "content": new_msg})
    holder = {"role": "assistant", "full": "", "tools": []}
    _chat_histories[task_id].append(holder)
    yield _chat_value(task_id)

    ws = Workspace(task_id)
    task = store.get_task(task_id)
    resume = (task or {}).get("session_id")
    sess = await SESSIONS.get_or_create(task_id, ws.root, resume_session_id=resume,
                                        with_builder_tools=True)

    full = ""
    async for ev in sess.respond(new_msg):
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
            store.update_task(task_id, status="done",
                              session_id=ev.get("session_id") or sess.session_id)
            _persist_chat(task_id)
            yield _chat_value(task_id)


async def stop_agent(task_id):
    if task_id:
        await SESSIONS.interrupt(task_id)
    return "已发送停止信号"


def preview_file(task_id, selection):
    def _sel_path(sel):
        if not sel:
            return ""
        item = sel[0] if isinstance(sel, list) else sel
        return getattr(item, "name", item) if not isinstance(item, str) else item
    path = _sel_path(selection)
    if not task_id or not path:
        return gr.update(value="// 选择文件查看", language="python")
    ws = Workspace(task_id)
    try:
        p = Path(path)
        try:
            rel = p.relative_to(ws.root)
        except ValueError:
            rel = p
        # path isolation: never read outside this task's workspace
        if not str(p.resolve()).startswith(str(ws.root.resolve())):
            return gr.update(value="// 禁止访问工作空间外文件", language="text")
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


async def start_preview_via_agent(task_id):
    """Submit a controlled start_preview action to the Builder Agent, which calls the
    real tool. The UI never starts the process directly."""
    if not task_id:
        return gr.update(value='<div class="empty">未选择任务</div>')
    device = store.get_device() or "cuda:0"
    entry = Workspace(task_id).project / "run.py"
    if not entry.exists():
        return gr.update(value=f'<div class="empty">未找到生成项目 {entry.name}，先生成 Agent</div>')
    action = (f'请立即调用 start_preview 工具启动预览：task_id={task_id}, device={device}。'
              f'启动成功后回复运行状态和 URL。')
    try:
        async for _ in stream_agent(task_id, action, []):
            pass
    except Exception as e:
        return gr.update(value=f'<div class="empty">启动异常：{_html.escape(str(e)[:120])}</div>')
    st = PREVIEWS.get(task_id)
    if st.status == "running":
        return gr.update(value=f'<iframe src="{st.url}" style="width:100%;height:70vh;border:none;border-radius:10px"></iframe>')
    return gr.update(value=f'<div class="empty">Agent 未启动预览：{_html.escape(st.error or st.status)}</div>')


async def stop_preview_via_agent(task_id):
    if not task_id:
        return gr.update(value='<div class="empty">未选择任务</div>')
    try:
        async for _ in stream_agent(task_id, f"请立即调用 stop_preview 工具停止预览：task_id={task_id}。", []):
            pass
    except Exception:
        pass
    return gr.update(value='<div class="empty">预览已停止</div>')


def select_task(task_id):
    """Restore chat, workspace root, status; stop any other task's preview."""
    if not task_id:
        return gr.update(), gr.update(), "未选择任务", gr.update(choices=[])
    _chat_histories[task_id] = Workspace(task_id).load_chat()
    # stop previews of OTHER tasks, not the selected one
    PREVIEWS.stop_all_except(task_id)
    st = PREVIEWS.get(task_id)
    prev_html = (f'<iframe src="{st.url}" style="width:100%;height:70vh;border:none;border-radius:10px"></iframe>'
                 if st.status == "running" else '<div class="empty">预览未启动</div>')
    t = store.get_task(task_id)
    status = (f'<span class="badge">{_html.escape(t.get("status",""))}</span> '
              f'设备：{store.get_device()} 任务：{task_id}')
    return (_chat_value(task_id), gr.update(root_dir=str(Workspace(task_id).root)),
            status, gr.update(choices=history_choices(task_id), value=task_id), prev_html)


def download_project_zip(task_id):
    if not task_id:
        return None
    ws = Workspace(task_id)
    out = config.DATA_DIR / f"{task_id}-project.zip"
    return ws.export_project_zip(out)


def status_badge(task_id):
    t = store.get_task(task_id)
    if not t:
        return "未选择任务"
    return (f'<span class="badge">{_html.escape(t.get("status",""))}</span> '
            f'设备：{store.get_device()} 任务：{task_id}')


# ---------------- layout ----------------
with gr.Blocks(title="Model2Agent", fill_width=True, fill_height=True) as demo:
    task_state = gr.State("")
    with gr.Row(equal_height=True, elem_classes="m2a-wrap"):
        # LEFT
        with gr.Column(scale=0, min_width=248, elem_classes="m2a-side"):
            gr.HTML('<div class="m2a-brand">Model2Agent</div>')
            new_btn = gr.Button("+ 新建任务", elem_classes="m2a-btn", size="sm")
            gr.HTML('<div class="dim" style="padding:4px 16px;font-size:12px">任务历史</div>')
            taskhist = gr.Radio(choices=history_choices(), label=None, show_label=False,
                                elem_id="taskhist", elem_classes="m2a-hist")

        # CENTER
        with gr.Column(scale=1, min_width=520, elem_classes="m2a-center"):
            with gr.Row(elem_classes="m2a-topbar"):
                gr.HTML("<div style='font-weight:600'>主 Agent 工作台</div>")
                status_html = gr.HTML(status_badge(""), elem_classes="m2a-status")
                stop_btn = gr.Button("停止", elem_classes="m2a-btn ghost", size="sm")
            chat = gr.Chatbot(height="64vh", show_label=False, elem_classes="m2a-chat", sanitize_html=False)
            with gr.Row(elem_classes="m2a-inputbar"):
                msg = gr.Textbox(placeholder="用自然语言描述下一步，或追问…", lines=2, scale=1, show_label=False, container=False)
                send = gr.Button("发送", elem_classes="m2a-btn")

        # RIGHT
        with gr.Column(scale=0, min_width=400, elem_classes="m2a-right"):
            with gr.Column(elem_classes="m2a-right-head"):
                with gr.Row():
                    gr.HTML("工作空间")
                with gr.Row():
                    prev_btn = gr.Button("启动预览", elem_classes="m2a-btn ghost", size="sm")
                    stop_prev = gr.Button("停止预览", elem_classes="m2a-btn ghost", size="sm")
                with gr.Row():
                    dl_btn = gr.Button("下载 ZIP", elem_classes="m2a-btn ghost", size="sm")
            with gr.Tabs():
                with gr.Tab("文件"):
                    fe = gr.FileExplorer(root_dir=str(config.WORKSPACES_DIR), scale=1, height=380, every=3)
                    prev = gr.Code(value="// 选择文件查看", language="python", interactive=False, lines=14)
                with gr.Tab("预览"):
                    preview_frame = gr.HTML('<div class="empty">预览未启动</div>')

    # DEVICE MODAL
    with gr.Column(visible=False, elem_classes="m2a-overlay") as dev_panel:
        with gr.Column(elem_classes="m2a-modalbox"):
            gr.HTML('<div style="font-size:18px;font-weight:700;margin-bottom:6px">设备配置</div>'
                    '<div class="dim" style="margin-bottom:14px">请选择本机真实可用的计算设备（仅一次，可随时修改）</div>')
            dev_radio = gr.Radio(choices=device_choices(), label="计算设备", value=None)
            dev_err = gr.HTML('<span style="color:#dc2626;font-size:13px"></span>')
            with gr.Row():
                save_dev = gr.Button("保存设备", elem_classes="m2a-btn")
                cancel_dev = gr.Button("取消", elem_classes="m2a-btn ghost")

    # NEW TASK FORM
    with gr.Column(visible=False, elem_classes="m2a-overlay") as new_panel:
        with gr.Column(elem_classes="m2a-modalbox"):
            gr.HTML('<div style="font-size:18px;font-weight:700;margin-bottom:14px">新建模型 Agent 任务</div>')
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
        lambda: (gr.update(visible=True), gr.update(choices=history_choices())), None, [new_panel, taskhist])
    cancel_dev.click(lambda: gr.update(visible=False), None, [dev_panel])
    cancel_form.click(lambda: gr.update(visible=False), None, [new_panel])

    create_btn.click(create_task, [name_in, goal_in, files_in], [task_state, msg, form_err]).then(
        lambda tid, first: (gr.update(visible=bool(tid)), gr.update(choices=history_choices(tid), value=tid),
                            gr.update(root_dir=str(Workspace(tid).root)) if tid else gr.update(),
                            status_badge(tid) if tid else gr.update()),
        [task_state, form_err], [new_panel, taskhist, fe, status_html]).then(
        stream_agent, [task_state, msg, chat], [chat])

    send.click(stream_agent, [task_state, msg, chat], [chat]).then(
        lambda: gr.update(value=""), None, [msg])

    taskhist.change(select_task, [taskhist], [chat, fe, status_html, taskhist, preview_frame])
    stop_btn.click(stop_agent, [task_state], [status_html])
    fe.select(preview_file, [task_state, fe], [prev])
    prev_btn.click(start_preview_via_agent, [task_state], [preview_frame])
    stop_prev.click(stop_preview_via_agent, [task_state], [preview_frame])
    dl_btn.click(download_project_zip, [task_state], [gr.File(label="下载", visible=False)])


if __name__ == "__main__":
    import os as _os
    demo.launch(server_name="0.0.0.0", server_port=int(_os.getenv("M2A_PORT", "7861")),
                inbrowser=False, css=CSS)
