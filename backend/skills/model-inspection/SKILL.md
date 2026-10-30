---
name: model-inspection
description: Inspect an uploaded model asset bundle to discover its framework, entrypoint, I/O schema, and dependencies. Use when a task first receives model assets.
---
# Model Inspection

Given an asset bundle under `inputs/`, discover:
1. **Framework**: read `manifest.json` (or detect) for `framework`, `task_family`, `model_id`.
2. **Entrypoint**: the Python file exposing inference callables (typically `infer.py`). List its public functions and signatures via AST.
3. **I/O schema**: from `examples.json` (`{"args": {...}}`) and docstrings — infer input types (image/CSV/text/tensor) and output shape.
4. **Weights**: the weight/state file (`*.pt`, `*.pth`, `*.bin`, `*.joblib`, `model.json`), its size and SHA256.
5. **Dependencies**: imports in the entrypoint (torch, sklearn, xgboost, transformers...).

Write your findings into `project/INSPECTION.md`. Never mutate the uploaded assets.
