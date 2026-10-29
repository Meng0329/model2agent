#!/usr/bin/env python3
"""CLI launcher for the cnn_digits Model Agent."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import agent
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import gradio as gr
        def q(x):
            import json; return json.dumps(agent.query(x), ensure_ascii=False, default=str)
        gr.Interface(fn=q, inputs="text", outputs="text", title="Model Agent: cnn_digits").launch()
    else:
        print(agent.query(" ".join(sys.argv[1:])))
