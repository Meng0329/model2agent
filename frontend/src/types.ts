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
  | { type: "tool_started"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string }
  | { type: "tool_completed"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string; result: string }
  | { type: "tool_failed"; task_id: string; run_id: string; seq: number; card_id: string; name: string; status: string; input: string; result: string }
  | { type: "workspace_changed"; task_id: string; run_id: string; seq: number }
  | { type: "preview_state_changed"; task_id: string; run_id: string; seq: number; state: string; url?: string; error?: string }
  | { type: "run_completed"; task_id: string; run_id: string; seq: number; text: string; is_error: boolean; session_id?: string; num_turns?: number }
  | { type: "run_failed"; task_id: string; run_id: string; seq: number; text: string; error?: string }
  | { type: "run_cancelled"; task_id: string; run_id: string; seq: number };
