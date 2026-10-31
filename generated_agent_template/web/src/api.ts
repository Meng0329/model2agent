import type { AgentConfig, RunResult, ToolCard, Uploaded } from "./types";

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

export async function runModel(capability: string, args: Record<string, unknown>): Promise<RunResult> {
  return j<RunResult>(
    await fetch(`${BASE}/api/model/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capability, args }),
    }),
  );
}

export async function upload(file: File, sid: string): Promise<Uploaded> {
  const fd = new FormData();
  fd.append("file", file);
  return j<Uploaded>(await fetch(`${BASE}/api/upload?sid=${encodeURIComponent(sid)}`, { method: "POST", body: fd }));
}

export async function interrupt(sid: string): Promise<void> {
  await fetch(`${BASE}/api/interrupt?sid=${encodeURIComponent(sid)}`, { method: "POST" });
}

export interface ChatEvent {
  type: "run_started" | "text_delta" | "tool_started" | "tool_completed" | "tool_failed" | "run_completed" | "run_failed";
  text?: string;
  card_id?: string;
  name?: string;
  status?: string;
  input?: string;
  result?: string;
  is_error?: boolean;
  seq?: number;
}

/**
 * POST /api/chat and consume the SSE response with a real streaming reader.
 * Requires the server to actually flush frames as they happen.
 */
export async function streamChat(
  sid: string,
  content: string,
  attachment: Uploaded | null,
  onEvent: (ev: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sid, content, attachment }),
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

function randomId(): string {
  // crypto.randomUUID() only exists in a SECURE CONTEXT (HTTPS or localhost).
  // This agent is typically opened over plain HTTP on a LAN IP, where it is
  // undefined — fall back to getRandomValues (works in insecure contexts too)
  // and finally Math.random for old WebViews.
  const c: Crypto | undefined = (globalThis as any).crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID().replace(/-/g, "");
  const bytes = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") c.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return hex;
}

export function newSid(): string {
  // one browser session id per tab (per-browser-session isolation)
  const k = "m2a_sid";
  let v = sessionStorage.getItem(k);
  if (!v) {
    v = randomId();
    sessionStorage.setItem(k, v);
  }
  return v;
}

export type { ToolCard, Uploaded };
