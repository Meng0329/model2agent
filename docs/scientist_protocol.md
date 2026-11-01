# Model2Agent V3.0 — Model-to-Scientist Research Protocol

> Status: S0 protocol + first S1 tasks. Every number in results must trace to
> `results/logs/scientist_runs.jsonl`. Unrun items are NOT_TESTED, blocked items
> are BLOCKED, failures are FAILED — never silently converted.

## 1. Scientist capability definition

A generated Scientist Agent is a **single main research agent + scientific Skills**
(MCP tools: `run_model`, `plan_experiment`, `record_evidence`,
`query_evidence_oracle`, `revise_hypothesis`) that can, for a given scientific
model and question:

1. state the question and known evidence;
2. form falsifiable hypotheses (with falsifier + predicted observation);
3. design controlled computational experiments with metrics;
4. execute the **real** model and observe outputs;
5. query **real historical measurements** within a budget;
6. record an auditable evidence ledger (E1–E4);
7. revise hypotheses on contradicting evidence;
8. conclude only what the evidence supports, with explicit limitations.

The **outer** Model2Agent compiler is a single Claude Agent SDK session with
subagents (`model-profiler`, `affordance-analyst`, `capability-graph-builder`,
`scientist-synthesizer`, `verification-auditor`). No fixed pipeline, no keyword
router, no simulation, no fallback.

## 2. Evidence taxonomy (enforced in code)

| Type | Meaning | May be reported as |
|---|---|---|
| E1 | model prediction | E1 only |
| E2 | independent computation | E2 only (not a physical fact) |
| E3 | historical real measurement | E3 (traceable source) |
| E4 | new experiment | E4 (only if actually run) |

`EvidenceRecord` rejects E3/E4 without `execution_evidence`.

## 3. Hypotheses

- **H1** Generated Scientist > general LLM + direct model calls on SISR.
- **H2** Closed-loop feedback > one-shot/fixed under equal budget (ASIG > 0).
- **H3** Grounded affordances + verification reduce unsupported claims (SEV).
- **H4** Frozen method generalizes to unseen scientific domains (HDSS).
- **H5** Compilation reduces manual engineering vs hand-built scientist agents.

Primary endpoint: **SISR**. Generalization endpoint: **HDSS** (NOT_TESTED this
round). Every hypothesis is falsifiable; no post-hoc change of primary endpoint.

## 4. Benchmark tasks (frozen)

`results/frozen/scientist_tasks.json` — 6 tasks, unique ids:

| Task | Domain | Split | Level | Oracle |
|---|---|---|---|---|
| protein-P1-novel | protein_science | novel | L4 | ProteinGym DMS (SDA_BACSU) |
| protein-P2-closed-loop | protein_science | closed_loop | L5 | ProteinGym DMS |
| protein-P3-rediscovery | protein_science | insight_rediscovery | L6 | ProteinGym DMS |
| rice-R1-novel | agriculture | novel | L4 | measured GRWT100 |
| rice-R2-closed-loop | agriculture | closed_loop | L5 | measured GRWT100 |
| rice-R3-rediscovery | agriculture | insight_rediscovery | L6 | measured GRWT100 |

Hidden measurements live only in `m2a_data/research/hidden/` (mode 0700, files
0600). Candidate input files contain ids only — no labels. A leakage test checks
this on every build.

## 5. Metrics

- **SISR** = pre-registered success (`input_resources.success_rule`) **and** real
  model calls > 0 **and** valid evidence records **and** required artifacts.
  Generation failure counts in the denominator.
- **SEV** = supported conclusions / concluded evidence; always reported together
  with `unsupported_claim_rate`. A conclusion is supported only when every cited
  evidence id resolves in the ledger (and declared types match). Because each
  generated scientist authors its own conclusion file, the evaluator accepts the
  unambiguous citation keys `supporting_evidence` / `supporting_records` /
  `evidence_ids` / `evidence` and statement keys `statement` / `claim` /
  `conclusion`. Alias acceptance never skips resolution — an unresolved citation
  still counts as unsupported.
- **ASIG** = adaptive minus fixed utility under equal budget (domain-normalized).
- **HDSS** = held-out-domain macro average (NOT_TESTED this round).
- Auxiliary: model calls, oracle queries, cost, latency, revisions, malformed records.

Success rules are machine-checked against the hidden oracle by the evaluator, not
by the agent.

**Harness corrections (2026-11-01).** Three pre-analysis harness defects were found and fixed;
the affected runs are preserved in `rep0_prebug/` / `rep0_budgetcap/` and labelled
`harness_*` in the ledger, excluded from method comparisons:
1. **Output path ambiguity** — the generated scientist wrote `final_selection.json` /
   `conclusions.jsonl` to the project cwd instead of the run out dir. Fixed by passing
   absolute output paths in the run query.
2. **Budget cap mismatch** — the runner applied a global $2.0 SDK cap instead of the task's
   declared `max_usd` (R2 = $3.0), cutting a session at $2.019 before it could deliver.
   Fixed: the per-task budget is authoritative for M and every baseline.
3. **Turn allowance** — closed-loop / rediscovery tasks need more turns than a single-pass
   ranking. `max_turns` is now a pre-registered per-task resource (L4 = 60, L5/L6 = 100),
   shared by M and all baselines.

None of these is a method change; all three make the harness honour the task contract that
baselines already use.

## 6. Baselines (fairness)

Same LLM (`deepseek-v4.1-flash`), same SDK (0.2.170), same task, same budget,
same candidate input, same success oracle.

- **B0** general LLM scientist — no model tools, no measurement oracle.
- **B1** LLM + model tools — real model + budgeted oracle, no SMSC structure.
- **B2** direct scientist synthesis — full workspace/asset, may write its own code.
- **B3** generic scientist scaffold — hand-written generic hypothesis/experiment loop.
- **M** full SMSC — generated single-session scientist project, run as a subprocess.

## 7. Statistics

Aggregate by task → model → domain; domain macro-average (equal weight). Paired
M-vs-baseline per task. With 2 models, results are descriptive only; no
cross-domain significance claim. Report effect size and uncertainty, not a single
p-value.

## 8. Stage gates

- **S0 gate**: schemas valid; unique task ids; no leakage; oracle budget enforced;
  strict comparison (no non-empty pass); scorers unit-tested. → PASSED (tests).
- **S1 gate**: ≥1 complete verifiable research task per domain; ≥1 task shows the
  next decision depends on real feedback; baselines share budget/task; failures
  reported honestly.
- **S2 gate** (partial this round): A5 (no feedback replanning), A6 (no independent
  verification), A1 (no SAD/graph), A9 (single vs multi outer agent).

## 9. Non-negotiables

No fabricated measurements, no E1-as-E3/E4, no simulated tool events, no silent
fallbacks, no tuning on held-out domains, secrets only in `.env`.
