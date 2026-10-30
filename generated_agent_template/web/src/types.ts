export interface AgentConfig {
  slug: string;
  model_id: string | null;
  framework: string | null;
  input_type: "image" | "tabular" | "text" | "vector" | string;
  adapter: string | null;
  vector_len: number | null;
  feature_names: string[] | null;
  labels: string[] | null;
  capabilities: string[];
  default_capability: string | null;
}

export interface ToolCard {
  id: string;
  name: string;
  status: "running" | "done" | "error";
  input?: string;
  result?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  cards?: ToolCard[];
  streaming?: boolean;
  error?: boolean;
}

export interface RunResult {
  capability: string;
  result: unknown;
}

export type Uploaded =
  | { input_type: "image"; features: number[]; vector_len: number }
  | { input_type: "tabular"; rows: { features: number[]; row: Record<string, string> }[] }
  | { input_type: "vector"; features: number[] }
  | { input_type: "text"; text: string };
