"""ChatGPT-style Gradio UI for the generated Model Agent. Adapts the direct
prediction input to the model's verified input type (from config.json).
Chat is driven by the agent's own Claude Agent SDK session (real streaming)."""
from __future__ import annotations
import asyncio
import html as _html
import json
from pathlib import Path

import gradio as gr

import model_exec

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
INPUT_TYPE = CFG.get("input_type", "vector64")
DEFAULT_CAP = CFG.get("default_capability", CFG["capabilities"][0])

_chat_hist = []


def _parse_features(raw: str):
    nums = [float(x) for x in raw.replace(",", " ").split() if x.strip()]
    return nums


def predict_direct(raw_input):
    """Direct deterministic prediction (real weights) — immediate, no LLM."""
    try:
        if INPUT_TYPE == "vector64":
            feats = _parse_features(raw_input)
            if len(feats) != 64:
                return f"输入错误：需要恰好 64 个数字，实际 {len(feats)} 个"
            args = {"features": feats}
        else:
            args = json.loads(raw_input)
        res = model_exec.run(DEFAULT_CAP, args)
        return json.dumps(res, ensure_ascii=False, default=str)
    except Exception as e:
        return f"错误: {type(e).__name__}: {e}"


def caps_html():
    return "<br>".join(f"· {_html.escape(c)}" for c in CFG["capabilities"])


async def chat_respond(prompt, history):
    from agent_core import GeneratedAgentSession
    sess = getattr(chat_respond, "_sess", None)
    if sess is None:
        sess = GeneratedAgentSession()
        chat_respond._sess = sess
    _chat_hist.append({"role": "user", "content": prompt})
    holder = {"role": "assistant", "content": ""}
    _chat_hist.append(holder)
    yield _chat_hist
    async for ev in sess.respond(prompt):
        if ev["type"] == "text":
            holder["content"] += ev["text"]
            yield _chat_hist
        elif ev["type"] == "result":
            yield _chat_hist


with gr.Blocks(title=f"Model Agent · {CFG['slug']}") as demo:
    gr.Markdown(f"### 🤖 {CFG['slug']} — Model Agent\n模型：{CFG['model_id']} · 框架：{CFG['framework']}")
    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot(height=420, show_label=False, sanitize_html=False)
            with gr.Row():
                m = gr.Textbox(placeholder="问模型 Agent：例如「对以下输入分类」「列出能力」…", scale=4, show_label=False, container=False)
                go = gr.Button("发送", variant="primary")
        with gr.Column(scale=2):
            gr.Markdown(f"**能力**\n{caps_html()}")
            gr.Markdown("### 直接推理（真实权重）")
            if INPUT_TYPE == "vector64":
                raw = gr.Textbox(label="输入（64 个数字，逗号/空格分隔）", lines=2)
            elif INPUT_TYPE == "tabular":
                raw = gr.File(label="上传 CSV")
            elif INPUT_TYPE == "image":
                raw = gr.Image(label="上传图片", type="filepath")
            else:
                raw = gr.Textbox(label="输入")
            pred = gr.Textbox(label="预测结果", interactive=False, lines=5)
            run_btn = gr.Button("运行推理", variant="primary")
    go.click(chat_respond, [m, chat], [chat]).then(lambda: "", None, [m])
    run_btn.click(predict_direct, [raw], [pred])


def launch(port: int = 7860):
    demo.launch(server_name="0.0.0.0", server_port=port, inbrowser=False)


if __name__ == "__main__":
    launch()
