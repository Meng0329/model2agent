export interface ImagePreprocess {
  ink_polarity: "ink_on_dark" | "ink_on_light";
  pixel_scale: number;
  canvas: [number, number];
}

export interface AgentUiInput {
  mode: "image" | "tabular" | "text" | "vector" | string;
  accept?: string;
  paste?: boolean;
  multiline?: boolean;
  dim?: number | null;
  feature_names?: string[] | null;
  sample?: number[] | null;
}

export interface AgentUiModel {
  slug: string;
  framework: string | null;
  input_type: string;
  labels: string[] | null;
  capabilities: string[];
  vector_len: number | null;
  feature_names: string[] | null;
}

export interface AgentUi {
  model: AgentUiModel;
  input: AgentUiInput;
  presets: string[];
  pipeline: string[];
  result_views: string[];
}

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
  image_preprocess?: ImagePreprocess | null;
  agent_ui?: AgentUi;
}

export interface Conversation {
  id: string;
  title: string;
  created_at?: number;
  updated_at?: number;
  message_count: number;
  last_preview?: string;
}

export interface ToolCard {
  id: string;
  name: string;
  status: "running" | "done" | "error";
  input?: string;
  result?: string;
}

export interface RunTrace {
  capability?: string;
  input_type?: string;
  latency_ms?: number;
  labels?: string[] | null;
  grid?: number[][];
  features?: number[];
  feature_names?: string[] | null;
  bbox?: [number, number, number, number];
  ink_polarity?: string;
}

export interface RunResult {
  capability: string;
  result: unknown;
  trace?: RunTrace;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  cards?: ToolCard[];
  streaming?: boolean;
  error?: boolean;
  attachment?: Uploaded | null;
  capability?: string | null;
}

export interface Uploaded {
  input_type: "image" | "tabular" | "vector" | "text";
  features?: number[];
  vector_len?: number;
  rows?: { features: number[]; row: Record<string, string> }[];
  trace?: RunTrace;
  text?: string;
}

export interface ApiEndpoint {
  method: string;
  path: string;
  summary: string;
  request?: unknown;
  snippets?: { curl: string; python: string; javascript: string };
}

export interface ApiDoc {
  title: string;
  version: string;
  swagger: string;
  openapi: string;
  model: AgentUiModel;
  endpoints: ApiEndpoint[];
  sse_events: string[];
}
