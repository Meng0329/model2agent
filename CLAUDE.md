# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Model2Agent — what this repo actually is

One repo, **two coupled layers** that share `model_assets/` and a single `.env`:

1. **V0.3 Research framework** (`model2agent/` + `scripts/`) — the *Paper2Agent-aligned* research pipeline. Scans a trained model asset, induces capabilities (AGCI), builds a capability graph (MCG), generates a standalone agent (Method M), verifies against **reference execution of the original model**, and runs benchmark/stats/robustness. This is the "method contribution" layer (AGCI/MCG are the claimed novelty; Skills are explicitly *not* a contribution).

2. **V2.0 Product** (`backend/` FastAPI + `frontend/` React + `generated_agent_template/`) — the *Builder* app. A real **Claude Agent SDK** session drives, per task, the conversion of an uploaded model asset into a standalone generated agent, previews it as a subprocess, and exports it as a ZIP. This is the user-facing product built on top of (and partially reusing the ideas of) layer 1.

The two layers are **not** wired together at runtime: the product's generation is deterministic `backend/generator.py` (template copy + real asset analysis), while `model2agent.orchestrator.run_method_m` is the research pipeline's separate LLM-driven path. Don't assume `backend/` calls `model2agent/` — it mostly doesn't.

# Architecture map

## Product (backend + frontend + template)

**Request flow (per task):**
`frontend/src` (React, Vite) → HTTP `/api/*` → `backend/routers/*` → either a direct handler or `backend/agent_bridge.AgentSession.respond()` which runs a real Claude Agent SDK subprocess. The SDK agent streams genuine `StreamEvent`s (text deltas + real tool cards) back over **SSE** (`GET /api/tasks/{id}/events`). The SSE event envelope is the contract between backend and frontend — see `frontend/src/types.ts` (`SseEvent`).

**The Builder agent's MCP tools** (`backend/agent_bridge._make_builder_tools`) are the only way generation/preview happen:
- `generate_agent(task_id, asset_dir)` → `backend/generator.generate()` scaffolds a standalone project from `generated_agent_template/` into `m2a_data/workspaces/<id>/project/`, copies real weights, writes `config.json`.
- `verify_agent(task_id)` → `backend/gen_cli.cmd_verify` boots the generated agent and runs its real `model_exec.py selfcheck`.
- `start_preview` / `stop_preview` → `backend/preview.PreviewManager` launches/stops the generated agent as an independent subprocess on a real free port (HTTP health-checked, never faked).

**Generation is deterministic Python, not LLM text.** `backend/generator.py` discovers the asset's real callables via `importlib`, infers `input_type` from grounded `examples.json`, computes `vector_len`, and resolves `labels` by a strict precedence (explicit → manifest/metrics → real `classes()` call → `true_label` fallback). The LLM only *decides when* to call `generate_agent`.

**Persisted state:** SQLite `m2a_data/v2.db` (`backend/db.py`) holds tasks/messages/settings/runs. The SDK session + workspace files live on disk under `m2a_data/workspaces/<id>/` (`backend/workspace.py`, which also does path-traversal-safe extraction and project ZIP export). **Neither is committed** (gitignored) — product data is runtime-only.

**Generated agent template (`generated_agent_template/`):** the standalone product every task becomes. Its `web/dist/` is **committed** (it's the shipped UI); `web/node_modules/` is not. `model_exec.py` loads the asset's native `infer.py` and exposes each discovered capability; `run.py` boots a FastAPI+uvicorn app.

**Frontend** is React + Tailwind v4 + Vite. Dev server proxies `/api` to the backend (see `vite.config.ts`, `changeOrigin:false` so the backend can build a host-aware preview iframe URL for remote browsers). `frontend/dist/` is served by FastAPI in prod.

## Research framework (model2agent + scripts)

`model2agent.orchestrator.run_method_m(bundle_dir)` runs the full pipeline: `agci/asset_scanner.scan_bundle` (AST + import evidence) → `agci/capability_inducer.induce_capabilities` (LLM) → `mcg/graph.build_mcg` → `builder/agent_builder.build_agent` (uniform template, *not* per-model hand-written) → `verification/reference_exec` (executes the **original** `infer.py` as ground truth at 3% float / 1e-6 prob tolerance; in fault-injection mode it compares against a *clean* oracle bundle so silent semantic drift is detectable).

`model2agent/llm.py` is the **single** LLM client for the research layer (OpenAI-compatible DeepSeek endpoint). All methods (M, B0, B2) route through it so cost/latency are measured identically — a fairness requirement. `scrub()` strips accidental key leakage before logging; `tests/test_core.py::test_no_secrets_in_logs_or_tracked_files` enforces this.

Baselines: `baselines/b0_raw_assets.py` (DeepSeek + raw asset), `b2_direct_synthesis.py` (direct generation), `b1_generic_wrapper.py`, `b3_*` reserved. Benchmark tasks/frozen ground truth live in `results/frozen/tasks.json` (committed). Per `docs/next_phase_plan.md`, P0 is the only executed phase; P1–P4 are plans, not done.

## Model assets (`model_assets/<slug>/`)

Each asset is a self-describing bundle the pipeline consumes:
- `manifest.json` — `slug`, `framework`, `task_family`, `entry_module`, `entry_functions`, `examples`, `weights_path`, `license`.
- `infer.py` — real inference entrypoints (must be importable; import failure is a hard scan error).
- `examples.json` — `{function: [{args, input?, true_label?}]}`; doubles as verification ground truth.
- weights (`*.pt` / `model.json` / `*.joblib`), `model_card.md`, `metrics.json` (feature names, labels).

Active assets: `cnn_digits` (PyTorch, image→64-vec), `xgb_tabular` (XGBoost, 30-vec tabular). `sklearn_digits` has **no labels/ground truth** (inference-only). `bert_zh` is **excluded** (transformers not installed, no portable weights).

# Commands

## Backend (product)
```bash
pip install -r requirements.txt                      # PEP668 → add --break-system-packages
cp .env.example .env                                 # fill DEEPSEEK_API_KEY (gitignored)
# The product server is expected on PORT 8100 (frontend proxy + acceptance both target 8100;
# backend/app.py's __main__ defaults to 8000, so pass --port 8100):
uvicorn backend.app:app --host 0.0.0.0 --port 8100
```
Backend also mounts `frontend/dist/` if present (prod). Dev: run `uvicorn` on 8100 and `npm run dev` (5173) in parallel.

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
pytest tests/test_core.py::test_scan_cnn_discovers_functions  # single test
python3 scripts/v2_acceptance.py                             # product gates vs backend on :8100
M2A_BASE=http://host:8100 python3 scripts/v2_acceptance.py
V2_DOCKER=1 python3 scripts/v2_acceptance.py                # also runs the REAL Docker build/boot/infer gate
```

## Research pipeline (needs .env + GPU)
```bash
python model_assets/<slug>/train.py   # train/freeze pilot weights
python scripts/freeze_tasks.py        # build benchmark + ground truth (reference execution)
python scripts/run_pilot.py --reps 5 --methods B0 B2 M
python scripts/run_analysis.py        # paired tests + cluster bootstrap 95% CI → results/csv + logs
python scripts/run_robustness.py      # 6-class fault injection
python scripts/make_figures.py       # Figures 1–5 (template-only where data missing)
```

# Invariants — do not break these

- **No fabricated agent behavior.** No mock tool events, no OpenAI fallback in the product, no keyword routing, no self-written agent loop. The only runtime is the Claude Agent SDK session in `backend/agent_bridge.py`. Acceptance tests fail on fakes.
- **Secrets are never in code, logs, or exported ZIPs.** Only `.env` (gitignored). `generated_agent_template/.env.example` is a placeholder by design. `backend/workspace.export_project_zip` and the acceptance `g_export_zip` both scan for real-key leakage.
- **Silent errors are not success.** Verification failures, tool errors, and unverified capabilities are recorded honestly; the failure-reporting docs (`results/failure_report.md`) require unexecuted experiments to be marked incomplete, never fabricated.
- **GPU policy differs by layer:** `model2agent/config.py` hardcodes `CUDA_VISIBLE_DEVICES=0` (research constraint). The *product* respects the **user-selected device** (`backend/preview.start` derives the index; no hardcoded GPU0). Don't reintroduce GPU0 assumptions into the product.
- **`generated_agent_template/web/dist/` is committed** — if you rebuild that UI, commit the result. `m2a_data/`, `frontend/dist/`, `frontend/node_modules/`, `*.zip`, and `results/logs/*.jsonl` are gitignored (runtime/output only). `results/frozen/tasks.json` is committed (it's the benchmark ground truth).
- **Generation must stay deterministic.** Never make `config.json` depend on LLM-guessed values; derive everything from the asset's manifest/examples/real calls.
