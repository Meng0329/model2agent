---
name: agent-testing
description: Run real tests against a generated Model Agent: weight selfcheck, its own SDK chat, and Gradio boot. Use before reporting success.
---
# Agent Testing

Verify the generated Agent end-to-end with real execution (in `project/`):
1. **Weights**: `python3 -c "import sys,json;sys.path.insert(0,'.');import model_exec;print(json.dumps(model_exec.selfcheck()))"`
   → real predictions on `examples.json` (never fabricate).
2. **Own SDK chat**: start `project/run.py` (`python3 run.py --port N`) and confirm the
   agent's own `agent_core.GeneratedAgentSession` answers and calls `run_model`.
3. **Boot**: `curl` the Gradio app for HTTP 200.

Report failures verbatim. Never mark untested or failed runs as success.
