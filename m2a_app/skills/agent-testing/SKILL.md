---
name: agent-testing
description: Run real tests against a generated Model Agent: import check, real-weight inference, multi-turn chat, and streamed tool execution. Use before reporting success.
---
# Agent Testing

Verify the generated Agent end-to-end with real execution:
1. `python project/runtime.py --selfcheck` loads the model and produces a real prediction.
2. Multi-turn SDK chat returns correct outputs.
3. The Gradio app boots and serves HTTP 200.
Report failures verbatim. Never mark untested or failed runs as success.
