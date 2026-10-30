---
name: agent-generation
description: Generate a standalone Model Agent project (its own SDK runtime + DeepSeek + Gradio UI + skills + Dockerfile) in the task workspace using the shared generator. Use after the model is inspected and executed.
---
# Agent Generation

To produce a complete, independently-runnable Agent project in `project/`, call the
deterministic generator (real tool work, not LLM text):

```python
import sys; sys.path.insert(0, "/data/mzb/paper2agent")
from m2a_app.generator import generate
proj = generate("<TASK_ID>", "<path to uploaded asset dir under inputs/>")
```

- `<TASK_ID>` is the current task id (from the workspace path).
- The asset dir is under `inputs/<slug>/` (the uploaded bundle).
- The generator copies the model-agnostic template, copies the REAL weights into
  `project/assets/<slug>/`, and writes `project/config.json` derived from the asset's
  manifest + examples (input type, capabilities). Never guess capabilities from the name.

Then verify with model-execution / agent-testing skills. The generated Agent has its
OWN Claude Agent SDK session — it never depends on the Builder's in-memory objects.
