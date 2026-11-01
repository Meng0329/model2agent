// Shared types for the Model2Agent V2.0 frontend.

export interface DeviceInfo {
  id: string;
  label: string;
  kind: string;
  name: string;
  total_gb: number | null;
  free_gb: number | null;
  available: boolean;
}

export interface Task {
  id: string;
  name: string;
  goal: string;
  status: string;
  session_id: string | null;
  device: string | null;
  asset_slug: string;
  workspace_path: string;
  has_generated: boolean;
  generated_at: string | null;
  preview_state: string;
  preview_url: string | null;
  preview_error: string | null;
  docker_status: string;
  created_at: string;
  updated_at: string;
}

export interface ToolCard {
  id: string;
  name: string;
  status: "running" | "done" | "error";
  input: string;
  result: string;
}

export interface Message {
  id: string;
  task_id: string;
  role: "user" | "assistant";
  content: string;
  tool_cards: ToolCard[];
  seq: number;
  created_at: string;
}

// SSE event envelope (see backend event protocol).
export type SseEvent =
  | { type: "run_started"; task_id: string; run_id: string; seq: number }
  | { type: "text_delta"; task_id: string; run_id: string; seq: number; text: string; message_id?: string }
  | { type: "thinking_delta"; task_id: string; run_id: string; seq: number; text: string }
  | { type: "tool_started"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string }
  | { type: "tool_completed"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string; result: string }
  | { type: "tool_failed"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string; result: string }
  | { type: "run_stage"; task_id: string; run_id: string; seq: number; stage: string; status: string; tool: string; round: number; evidence: string }
  | { type: "workspace_changed"; task_id: string; run_id: string; seq: number }
  | { type: "preview_state_changed"; task_id: string; run_id: string; seq: number; state: string; url?: string; error?: string }
  | { type: "run_completed"; task_id: string; run_id: string; seq: number; text: string; is_error: boolean; session_id?: string; num_turns?: number }
  | { type: "run_failed"; task_id: string; run_id: string; seq: number; text: string; error?: string }
  | { type: "run_cancelled"; task_id: string; run_id: string; seq: number };

// ---- Model-to-Scientist benchmark (read-only dashboard) ----
export interface ScientistCell {
  n: number;
  status: "OBSERVED" | "FAILED" | "NOT_TESTED";
  sisr_rate?: number | null;
  oracle_ok_rate?: number | null;
  mean_sev?: number | null;
  mean_cost_usd?: number | null;
  mean_latency_s?: number | null;
}

export interface ScientistRun {
  run_id: string;
  stage: string;
  method_id: string;
  scientific_task_id: string;
  scientific_domain: string;
  scientific_task_success: boolean;
  final_conclusion_validity: boolean;
  evidence_validity: number | null;
  model_call_count: number | null;
  experiment_count: number | null;
  adaptation_success: boolean;
  cost: number | null;
  latency: number | null;
  failure_category: string | null;
  notes: string | null;
  artifact_path: string | null;
}

export interface ScientistTask {
  task_id: string;
  domain: string;
  scientific_model: string;
  split: string;
  capability_level: string;
  scientific_question: string;
  success_rule: Record<string, unknown> | null;
  budget: Record<string, unknown>;
  has_hidden_oracle: boolean;
  expected_artifacts: string[];
}

export interface ScientistBenchmark {
  tasks: ScientistTask[];
  by_method: Record<string, ScientistCell>;
  cells: Record<string, Record<string, ScientistCell>>;
  n_runs: number;
  n_harness_runs: number;
}

export interface ScientistRunDetail {
  run: Record<string, unknown>;
  result: Record<string, unknown> | null;
  conclusions: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  final_selection: { top_ids?: string[] } | null;
  revisions: Record<string, unknown>[];
  oracle_queries: number | null;
  harness_artifact_note: string;
}
