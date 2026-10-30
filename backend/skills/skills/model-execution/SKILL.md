---
name: model-execution
description: Execute the discovered model inference entrypoint against real weights to validate outputs. Use after model-inspection.
---
# Model Execution

To validate a discovered entrypoint:
- Load it via importlib (unique module name to avoid global collisions).
- Run each public inference function on the first example in `examples.json`.
- Record the real output. This is the *ground truth* — never fabricate it.

Set the runtime device from the task's selected device (e.g. `CUDA_VISIBLE_DEVICES=0`).
Only load trusted, project-local code. Do not execute untrusted uploads outside the workspace.
