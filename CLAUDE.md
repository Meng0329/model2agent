# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Model2Agent — what this repo actually is

One repo, **two layers** that share `model_assets/` and a single `.env`:

1. **V3.0 Research main line — Model-to-Scientist** (`model2agent/scientist/` + `model2agent/oracle/`
   + `scripts/run_scientist_*.py`). Converts ONE pretrained scientific model into an autonomous
   domain-scientist agent that states falsifiable hypotheses, designs controlled computational
   experiments, executes the **real** model, queries **real historical measurements** within a
   budget, revises on contradicting evidence, and concludes only what the evidence supports.
   The outer compiler is a **single Claude Agent SDK session with subagents** (no fixed pipeline,
   no keyword routing, no simulation, no fallback). The generated Scientist is a single main agent
   + scientific Skills. This is the method contribution (SMSC).

2. **V2.0 Product** (`backend/` FastAPI + `frontend/` React + `generated_agent_template/`) — the
   *Builder* app. A real **Claude Agent SDK** session drives, per task, the conversion of an
   uploaded model asset into a standalone generated agent, previews it as a subprocess, and
   exports it as a ZIP. This is the user-facing product built on top of (and partially reusing the
   ideas of) layer 1. This round the research line is the focus; frontend is not modified.

The two layers are **not** wired together at runtime. The product's generation is deterministic
`backend/generator.py`; the research line's generation is agent-driven
`model2agent/orchestrator.run_smsc`. Don't assume `backend/` calls `model2agent/` — it mostly doesn't.

# Architecture map

## Product (backend + frontend + template)

**Request flow (per task):**
`frontend/src` (React, Vite) → HTTP `/api/*` → `backend/routers/*` → either a direct handler or
`backend/agent_bridge.AgentSession.respond()` which runs a real Claude Agent SDK subprocess. The
SDK agent streams genuine `StreamEvent`s (text deltas + real tool cards) back over **SSE**
(`GET /api/tasks/{id}/events`). The SSE event envelope is the contract between backend and
frontend — see `frontend/src/types.ts` (`SseEvent`).

**ONE foundation.** The product's outer agent is the **Model-to-Scientist single-session
multi-agent compiler** — the same scientist kit as the research line
(`model2agent/scientist/sdk_session.py` + `BUILDER_AGENTS` + `make_builder_tools`), driven by
`backend/agent_bridge.AgentSession` via `stream_session`. There is no separate "old V2 Builder"
session. The only difference from a research run: the product session is built with
`env_override=backend.config.agent_env()` (user-selected device, NO hardcoded GPU0) and it uses
the product MCP tools (below) to produce the artifact.

**The outer agent's MCP tools** (`backend/agent_bridge._make_builder_tools`) are the only way
generation/preview happen:
- `generate_agent(task_id, asset_dir)` → `backend/generator.generate()` scaffolds a standalone
  project from `generated_agent_template/` into `m2a_data/workspaces/<id>/project/`, copies real
  weights, writes `config.json`.
- `verify_agent(task_id)` → `backend/gen_cli.cmd_verify` boots the generated agent and runs its
  real `model_exec.py selfcheck`.
- `start_preview` / `stop_preview` → `backend/preview.PreviewManager` launches/stops the generated
  agent as an independent subprocess on a real free port (HTTP health-checked, never faked).

**Generation is deterministic Python, not LLM text.** `backend/generator.py` discovers the asset's
real callables via `importlib`, infers `input_type` from grounded `examples.json`, computes
`vector_len`, and resolves `labels` by a strict precedence (explicit → manifest/metrics → real
`classes()` call → `true_label` fallback). The LLM only *decides when* to call `generate_agent`.

**Persisted state:** SQLite `m2a_data/v2.db` (`backend/db.py`) holds tasks/messages/settings/runs.
The SDK session + workspace files live on disk under `m2a_data/workspaces/<id>/`
(`backend/workspace.py`, which also does path-traversal-safe extraction and project ZIP export).
**Neither is committed** (gitignored) — product data is runtime-only.

**Generated agent template (`generated_agent_template/`):** the standalone product every task
becomes. Its `web/dist/` is **committed** (it's the shipped UI); `web/node_modules/` is not.
`model_exec.py` loads the asset's native `infer.py` and exposes each discovered capability;
`run.py` boots a FastAPI+uvicorn app.

**Frontend** is React + Tailwind v4 + Vite. Dev server proxies `/api` to the backend (see
`vite.config.ts`, `changeOrigin:false` so the backend can build a host-aware preview iframe URL
for remote browsers). `frontend/dist/` is served by FastAPI in prod.

## Research main line (model2agent + scripts)

- `model2agent.orchestrator.run_smsc(bundle_dir, task, project_dir)` — one `ClaudeSDKClient`
  session with `BUILDER_AGENTS` (model-profiler, affordance-analyst, capability-graph-builder,
  scientist-synthesizer, verification-auditor). No fixed pipeline/order; the agent delegates as it
  sees fit. Only deterministic code is oracle execution, ledger persistence, budget accounting,
  scoring, run records, and SDK/env assembly.
- `model2agent/scientist/` — `schemas.py` (typed, validated), `subagents.py` (AgentDefinition),
  `sdk_session.py` (StreamEvent/ResultMessage parsing, `setting_sources=[]` isolation),
  `model_introspection.py` (real AST + import + example execution + sha256),
  `evidence.py` (append-only Run/Evidence ledger), `budget.py` (raises, never clamps),
  `scorer.py` (SISR + SEV over conclusions with citation resolution),
  `runner.py` (independent subprocess + oracle-based evaluation), `methods.py` (fair baselines
  B0–B3), `runtime/` (self-contained generated-scientist project).
- `model2agent/oracle/` — `execution_oracle.py` (strict recursive numeric compare, rejects None,
  no "non-empty pass"), `historical_oracle.py` (real measurement replay, budget-accounted,
  access-logged, hidden store mode 0700).
- There is no separate "LLM client" module: every model call goes through the Claude Agent SDK
  session (`model2agent/scientist/sdk_session.py`). `tests/test_core.py::
  test_no_secrets_in_logs_or_tracked_files` enforces that no real API key ever reaches logs or
  tracked files.

Baselines B0/B1/B2/B3 and M share the same LLM (`deepseek-v4.1-flash`), the same SDK, the same
task, the same budget, the same candidate input, and the same success oracle — only structure
differs. Frozen benchmark + ground truth live in `results/frozen/scientist_tasks.json` (committed,
unique task ids). The append-only reproducibility ledger is `results/logs/scientist_runs.jsonl`
(committed). Protocol: `docs/scientist_protocol.md`.

## Model assets (`model_assets/<slug>/`)

Each asset is a self-describing bundle the pipeline consumes:
- `manifest.json` — `slug`, `framework`, `task_family`, `entry_module`, `entry_functions`,
  `examples`, `weights_path`, `license`.
- `infer.py` — real inference entrypoints (must be importable; import failure is a hard error).
- `examples.json` — `{function: [{args, input?, true_label?}]}`; doubles as verification ground truth.
- weights (`*.pt` / `model.json` / `*.joblib`), `model_card.md`, `metrics.json`, `scientific.json`.

Active scientific assets: `esm2_variant` (ESM-2 650M zero-shot masked-marginal ΔLLR, protein
variant scoring, GPU0) and `rice_gs` (Ridge genomic prediction, 2000 train-only variance-pruned
SNPs, 2259 lines, trait GRWT100). `cnn_digits`/`xgb_tabular` remain for product/unit tests.

# Commands

## Backend (product)
```bash
pip install -r requirements.txt                      # PEP668 → add --break-system-packages
cp .env.example .env                                 # fill DEEPSEEK_API_KEY (gitignored)
# The product server is expected on PORT 8100 (frontend proxy + acceptance both target 8100;
# backend/app.py's __main__ defaults to 8000, so pass --port 8100):
uvicorn backend.app:app --host 0.0.0.0 --port 8100
```
Backend also mounts `frontend/dist/` if present (prod). Dev: run `uvicorn` on 8100 and
`npm run dev` (5173) in parallel.

## Frontend
```bash
cd frontend && npm install
npm run dev          # Vite dev server, http://localhost:5173, proxies /api → :8100
npm run build        # tsc -b && vite build → frontend/dist (served by FastAPI)
npm run test         # Playwright e2e (frontend/e2e/*.spec.ts)
```

## Generated-agent template UI (separate build, only when regenerating the shipped UI)
```bash
cd generated_agent_template/web && npm install && npm run build   # produces web/dist (committed)
```

## Tests
```bash
pytest tests/                                                 # core suite (no LLM calls)
python3 scripts/v2_acceptance.py                             # product gates vs backend on :8100
M2A_BASE=http://host:8100 python3 scripts/v2_acceptance.py
V2_DOCKER=1 python3 scripts/v2_acceptance.py                # also runs the REAL Docker gate
```

## Scientist research line (needs .env + GPU0)
```bash
python3 scripts/build_scientist_benchmark.py      # frozen tasks + hidden oracles (0700/600)
python3 scripts/run_scientist_pilot.py --stage S1 --methods B0 B1 B2 B3 M --reps 1
python3 scripts/run_scientist_analysis.py         # SISR/SEV/cost/paired deltas + per-method domain macro
```
Run one task at a time; every run appends to `results/logs/scientist_runs.jsonl`. The pilot
summary JSON is regenerated by the analysis script — the ledger is the source of truth.

# Invariants — do not break these

- **No fabricated agent behavior.** No mock tool events, no OpenAI fallback, no keyword routing,
  no self-written agent loop, no simulation, no silent fallback. The only runtimes are Claude
  Agent SDK sessions (builder in `model2agent/orchestrator.py`; generated scientist in
  `m2a_scientist_runtime`; product in `backend/agent_bridge.py`, which now runs the SAME
  `model2agent/scientist` session as the research line). Acceptance/unit tests fail on fakes.
- **Secrets are never in code, logs, or exported ZIPs.** Only `.env` (gitignored).
  `backend/workspace.export_project_zip` and the acceptance `g_export_zip` both scan for real-key
  leakage; `tests/test_core.py::test_no_secrets_in_logs_or_tracked_files` scans logs and tracked
  files.
- **Silent errors are not success.** Verification failures, tool errors, unverified capabilities,
  and unrun experiments are recorded honestly (OBSERVED / NOT_TESTED / BLOCKED / FAILED), never
  fabricated or silently converted. The run ledger and the protocol's stage gates require this.
- **GPU policy differs by layer:** the research line hardcodes `CUDA_VISIBLE_DEVICES=0` (single
  GPU constraint). The *product* respects the **user-selected device** (no hardcoded GPU0). Don't
  reintroduce GPU0 assumptions into the product.
- **`generated_agent_template/web/dist/` is committed** — if you rebuild that UI, commit the
  result. `m2a_data/`, `frontend/dist/`, `frontend/node_modules/`, `*.zip`, and
  `results/experiments/**/trajectory.jsonl` are gitignored. `results/frozen/scientist_tasks.json`
  and `results/logs/scientist_runs.jsonl` are committed (benchmark ground truth + reproducibility
  ledger).
- **Generation determinism applies to the product.** Never make the product's `config.json`
  depend on LLM-guessed values; derive it from the asset's manifest/examples/real calls. The
  research line's scientist generation IS agent-driven, but the ledger/scoring/oracle code that
  judges it is deterministic and must never depend on the agent's prose.
- **No two versions of the method.** The old AGCI/MCG/Model→Tool pipeline is removed. Do not
  reintroduce a parallel "old path"; extend the SMSC main line in place. Likewise there is ONE
  product outer-agent foundation: the scientist session (`model2agent/scientist/sdk_session.py`
  + `BUILDER_AGENTS`). Do not reintroduce the old V2 Builder session (preset `claude_code` +
  `_BUILDER_APPEND`); the product artifact is still produced by the unchanged deterministic
  `generate_agent` / `verify_agent`, so the template and its adaptation stay identical.
