import type { AgentConfig, ApiDoc, Conversation, RunResult, ToolCard, Uploaded } from "./types";

// Relative base so the UI works both standalone (document at "/") and embedded
// behind the dashboard's same-origin preview proxy ("/api/tasks/<id>/preview/proxy/").
const BASE = ".";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${t ? ` — ${t.slice(0, 300)}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchConfig(): Promise<AgentConfig> {
  return j<AgentConfig>(await fetch(`${BASE}/api/config`));
}

export async function fetchHealth(): Promise<{ ok: boolean; slug: string; input_type: string }> {
  return j(await fetch(`${BASE}/api/health`));
}

export async function fetchApiDocs(): Promise<ApiDoc> {
  return j<ApiDoc>(await fetch(`${BASE}/api/apidocs`));
}

// ---- conversations -------------------------------------------------------
export async function listConversations(): Promise<Conversation[]> {
  const r = await j<{ conversations: Conversation[] }>(await fetch(`${BASE}/api/conversations`));
  return r.conversations;
}

export async function createConversation(title?: string): Promise<Conversation> {
  return j<Conversation>(await fetch(`${BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title ?? null }),
  }));
}

export async function conversationMessages(cid: string): Promise<{ conversation_id: string; messages: ChatMessage[] }> {
  return j(await fetch(`${BASE}/api/conversations/${encodeURIComponent(cid)}/messages`));
}

export async function deleteConversation(cid: string): Promise<void> {
  await fetch(`${BASE}/api/conversations/${encodeURIComponent(cid)}`, { method: "DELETE" });
}

// ---- inference -----------------------------------------------------------
export async function runModel(capability: string, args: Record<string, unknown>, trace = false): Promise<RunResult> {
  return j<RunResult>(await fetch(`${BASE}/api/model/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability, args, trace }),
  }));
}

export async function upload(file: File, conversationId: string): Promise<Uploaded> {
  const fd = new FormData();
  fd.append("file", file);
  return j<Uploaded>(await fetch(`${BASE}/api/upload?conversation_id=${encodeURIComponent(conversationId)}`, {
    method: "POST", body: fd,
  }));
}

export async function interrupt(conversationId: string): Promise<void> {
  await fetch(`${BASE}/api/interrupt?conversation_id=${encodeURIComponent(conversationId)}`, { method: "POST" });
}

// ---- chat SSE ------------------------------------------------------------
export interface ChatEvent {
  type: "run_started" | "text_delta" | "tool_started" | "tool_completed" | "tool_failed"
      | "model_run" | "run_completed" | "run_failed";
  text?: string;
  card_id?: string;
  name?: string;
  status?: string;
  input?: string;
  result?: unknown;
  trace?: unknown;
  capability?: string;
  is_error?: boolean;
  conversation_id?: string;
  seq?: number;
}

export async function streamChat(
  conversationId: string,
  content: string,
  attachment: Uploaded | null,
  onEvent: (ev: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, content, attachment }),
    signal,
  });
  if (!res.ok || !res.body) {
    const t = await res.text().catch(() => "");
    throw new Error(`chat ${res.status}: ${t.slice(0, 300)}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          onEvent(JSON.parse(raw) as ChatEvent);
        } catch {
          /* ignore malformed frame */
        }
      }
    }
  }
}

export type { ToolCard, Uploaded, ChatMessage };
import type { ChatMessage } from "./types";
