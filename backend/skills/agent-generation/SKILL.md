---
name: agent-generation
description: Generate a standalone Model Agent project (its own SDK runtime + DeepSeek + Gradio UI + skills + Dockerfile) in the task workspace using the shared generator. Use after the model is inspected and executed.
---
# Agent Generation

To produce a complete, independently-runnable Agent project in `project/`, call the
deterministic generator (real tool work, not LLM text). The repo root is 3 levels up
from the task workspace (`m2a_data/workspaces/<TASK_ID>/`), so use a RELATIVE import
that works on any machine:

```python
import sys
from pathlib import Path
repo = Path.cwd().resolve().parents[2]      # .../model2agent  (portable, no hardcoded host path)
sys.path.insert(0, str(repo))
from m2a_app.generator import generate
asset_dir = [p for p in Path("inputs").iterdir() if p.is_dir()][0]   # uploaded bundle
proj = generate(Path.cwd().name, str(asset_dir))
```

- The generator copies the model-agnostic template, copies the REAL weights into
  `project/assets/<slug>/`, and writes `project/config.json` derived from the asset's
  manifest + examples (input type, capabilities). Never guess capabilities from the name.
- The generated Agent has its OWN Claude Agent SDK session — it never depends on the
  Builder's in-memory objects.

Then verify with model-execution / agent-testing skills.
