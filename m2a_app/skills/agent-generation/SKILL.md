---
name: agent-generation
description: Generate a standalone Model Agent project (SDK runtime + DeepSeek + Gradio UI + skills + Dockerfile) in the task workspace. Use after the model is inspected and executed.
---
# Agent Generation

Produce a complete, independently-runnable Agent project in `project/`:
- `runtime.py`: Claude Agent SDK runtime (`ClaudeSDKClient`) pointed at the Anthropic-compatible DeepSeek endpoint.
- `agent.py`: capability routing + multi-turn chat.
- `app.py`: ChatGPT-style Gradio UI adapted to the model's real I/O type (image upload / CSV upload / text input).
- `skills/`: model-specific skills.
- `model_exec.py`: loads real weights, exposes inference functions.
- `Dockerfile`, `requirements.txt`, `.env.example`, `README.md`.

The generated Agent must call REAL weights and must have its OWN SDK session —
never depend on the Builder's in-memory objects.
