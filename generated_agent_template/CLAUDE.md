# Generated Model Agent — scope

This project is the standalone Model Agent generated for a single trained model
asset (`assets/<slug>/`). It is NOT part of the Model2Agent Builder platform.

- **Scope**: only this model asset, its real inference (`infer.py`), the endpoints
  defined in `app.py`, and the `model-execution` skill.
- **Never** reference, read, or leak the Builder platform's internals (repos,
  other models, internal docs) into conversation or output.
- **Grounding**: every prediction/answer must come from real weights via
  `model_exec.run`. Never fabricate a value or claim verification that did not run.
- **AI-native**: per-model input UI, the 3 preset questions, and the execution
  pipeline are declared in `agent_ui.json`; the runtime renders them generically.
- **No fallback**: inputs the asset does not declare are a hard error, not guessed.
