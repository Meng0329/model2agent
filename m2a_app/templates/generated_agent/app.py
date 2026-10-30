"""ChatGPT-style Gradio UI for the generated Model Agent. Adapts the direct
prediction input to the model's verified input type (from config.json).
Chat is driven by the agent's own Claude Agent SDK session (real streaming)."""
from __future__ import annotations
import json
from pathlib import Path

import gradio as gr

import model_exec

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
INPUT_TYPE = CFG.get("input_type", "vector64")
VECTOR_LEN = CFG.get("vector_len")
DEFAULT_CAP = CFG.get("default_capability", CFG["capabilities"][0])

ACCENT = "#00a3a6"
CSS = """
:root{--accent:#00a3a6;--bg:#f8fafc;--panel:#fff;--border:#e5e7eb;--text:#1e293b;--muted:#64748b}
*{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif}
body{background:var(--bg);color:var(--text)}
.gradio-container{max-width:none!important;padding:0!important}
.m2a-row{display:flex;gap:18px;align-items:flex-start;padding:18px;max-width:1500px;margin:0 auto}
body{background:var(--bg);color:var(--text)}
.m2a-brand{font-weight:700;font-size:17px;color:var(--accent);letter-spacing:.2px}
.m2a-sub{color:var(--muted);font-size:13px;margin-top:2px}
.m2a-cap{display:inline-block;font-size:12px;padding:3px 10px;border-radius:9999px;background:#ccfbf1;color:#0f766e;font-weight:600;margin:2px 4px 2px 0}
.m2a-card{background:#fff;border:1px solid var(--border);border-radius:0.875rem;padding:16px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.m2a-btn{background:var(--accent)!important;color:#fff!important;border:none!important;border-radius:0.625rem!important;font-weight:600!important}
.m2a-btn:hover{filter:brightness(.95)}
"""


def _parse_features(raw: str):
    return [float(x) for x in str(raw).replace(",", " ").split() if weak_ok(x)]


def weak_ok(x):
    try:
        float(x); return True
    except Exception:
        return False


def predict_direct(raw_input):
    """Direct deterministic prediction (real weights) — immediate, no LLM."""
    try:
        if INPUT_TYPE in ("vector64", "vector"):
            feats = _parse_features(raw_input)
            if VECTOR_LEN and len(feats) != VECTOR_LEN:
                return f"输入错误：需要恰好 {VECTOR_LEN} 个数字，实际 {len(feats)} 个"
            args = {"features": feats}
        else:
            args = json.loads(raw_input)
        res = model_exec.run(DEFAULT_CAP, args)
        return json.dumps(res, ensure_ascii=False, default=str)
    except Exception as e:
        return f"错误: {type(e).__name__}: {e}"


def caps_html():
    return "".join(f'<span class="m2a-cap">{c}</span>' for c in CFG["capabilities"])


async def chat_respond(prompt, history):
    from agent_core import GeneratedAgentSession
    sess = getattr(chat_respond, "_sess", None)
    if sess is None:
        sess = GeneratedAgentSession()
        chat_respond._sess = sess
    hist = list(history or [])
    hist.append({"role": "user", "content": prompt})
    holder = {"role": "assistant", "content": ""}
    hist.append(holder)
    yield hist
    async for ev in sess.respond(prompt):
        if ev["type"] == "text":
            holder["content"] += ev["text"]
            yield hist
        elif ev["type"] == "result":
            yield hist


with gr.Blocks(title=f"Model Agent · {CFG['slug']}", fill_width=True, fill_height=True) as demo:
    with gr.Row(elem_classes="m2a-row"):
        gr.HTML(f'<div class="m2a-brand">🤖 {CFG["slug"]} · Model Agent</div>'
                f'<div class="m2a-sub">模型 {CFG["model_id"]} · 框架 {CFG["framework"]} · 由 Model2Agent 生成</div>')
    with gr.Row(equal_height=True, elem_classes="m2a-row"):
        with gr.Column(scale=3, min_width=460):
            chat = gr.Chatbot(height=520, show_label=False, sanitize_html=False, elem_classes="m2a-card")
            with gr.Row():
                m = gr.Textbox(placeholder="问模型 Agent：例如「对以下输入分类」「列出能力」…", scale=4,
                               show_label=False, container=False)
                go = gr.Button("发送", elem_classes="m2a-btn")
        with gr.Column(scale=2, min_width=320):
            gr.HTML('<div class="m2a-card"><div style="font-weight:600;margin-bottom:8px">能力</div>'
                    f'{caps_html()}</div>')
            with gr.Group(elem_classes="m2a-card"):
                gr.HTML('<div style="font-weight:600;margin-bottom:8px">直接推理（真实权重）</div>')
                if INPUT_TYPE == "vector64":
                    lbl = f"输入（{VECTOR_LEN or 64} 个数字，逗号/空格分隔）"
                    raw = gr.Textbox(label=lbl, lines=2)
                elif INPUT_TYPE == "vector":
                    lbl = f"输入（{VECTOR_LEN or '若干'} 个数字，逗号/空格分隔）"
                    raw = gr.Textbox(label=lbl, lines=2)
                elif INPUT_TYPE == "tabular":
                    raw = gr.File(label="上传 CSV")
                elif INPUT_TYPE == "image":
                    raw = gr.Image(label="上传图片", type="filepath")
                else:
                    raw = gr.Textbox(label="输入")
                pred = gr.Textbox(label="预测结果", interactive=False, lines=6)
                run_btn = gr.Button("运行推理", elem_classes="m2a-btn")
    go.click(chat_respond, [m, chat], [chat]).then(lambda: "", None, [m])
    run_btn.click(predict_direct, [raw], [pred])


def launch(port: int = 7860):
    demo.launch(server_name="0.0.0.0", server_port=port, inbrowser=False, css=CSS)


if __name__ == "__main__":
    launch()
