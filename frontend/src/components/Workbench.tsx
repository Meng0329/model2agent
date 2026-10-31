// Center panel: multi-turn chat with the Builder Agent (real SSE stream).
import { useEffect, useRef, useState } from "react";
import { PaperPlaneRight, Stop, Robot, TerminalWindow, CheckCircle, XCircle, CircleNotch } from "@phosphor-icons/react";
import type { Task, ToolCard, SseEvent } from "../types";
import { api } from "../lib/api";
import { EventStream } from "../lib/sse";
import { cn, Badge } from "./ui";

interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_cards: ToolCard[];
  streaming: boolean;
}

export function Workbench({ task }: { task: Task }) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [value, setValue] = useState("");
  const [running, setRunning] = useState(false);
  const [runSeq, setRunSeq] = useState(0); // last consumed event seq (reconnect-safe)
  const [err, setErr] = useState("");
  const streamRef = useRef<EventStream | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const taskId = task.id;

  // auto-grow the composer with its content (capped), so it floats over a
  // unified background instead of using a fixed-height input bar.
  const autoGrow = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };
  useEffect(() => { autoGrow(); }, [value]);

  // load persisted messages on task switch
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`/api/tasks/${taskId}/messages`).then((r) => r.json());
        if (!alive) return;
        const msgs: UiMessage[] = (r.messages as any[]).map((m) => ({
          id: m.id, role: m.role, content: m.content,
          tool_cards: m.tool_cards || [], streaming: false,
        }));
        setMessages(msgs);
      } catch { /* ignore */ }
    })();
    return () => { alive = false; };
  }, [taskId]);

  // auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const stopStream = () => { streamRef.current?.close(); streamRef.current = null; };

  const onEvent = (e: SseEvent) => {
    setRunSeq(e.seq);
    if (e.type === "run_started") {
      setRunning(true); setErr("");
      setMessages((prev) => [...prev, { id: `a-${e.run_id}`, role: "assistant", content: "", tool_cards: [], streaming: true }]);
    } else if (e.type === "text_delta") {
      setMessages((prev) => prev.map((m) => (m.id === `a-${e.run_id}` ? { ...m, content: m.content + e.text } : m)));
    } else if (e.type === "tool_started" || e.type === "tool_completed" || e.type === "tool_failed") {
      setMessages((prev) => prev.map((m) => {
        if (m.id !== `a-${e.run_id}`) return m;
        const cards = [...m.tool_cards];
        const i = cards.findIndex((c) => c.id === e.card_id);
        const card: ToolCard = { id: e.card_id, name: e.name, status: e.status as ToolCard["status"], input: e.input, result: (e as any).result ?? "" };
        if (i >= 0) cards[i] = card; else cards.push(card);
        return { ...m, tool_cards: cards };
      }));
    } else if (e.type === "run_completed" || e.type === "run_failed") {
      setRunning(false);
      setMessages((prev) => prev.map((m) => (m.id === `a-${e.run_id}` ? { ...m, streaming: false } : m)));
      stopStream();
    } else if (e.type === "run_cancelled") {
      setRunning(false);
      stopStream();
    }
  };

  const send = async () => {
    if (!value.trim() || running) return;
    const text = value.trim();
    setValue("");
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", content: text, tool_cards: [], streaming: false }]);
    // (re)open SSE subscription for reconnect-safety
    stopStream();
    streamRef.current = new EventStream(taskId, onEvent, undefined, runSeq);
    streamRef.current.start();
    try {
      const r = await fetch(`/api/tasks/${taskId}/messages`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: text }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setErr(d.detail || `请求失败 ${r.status}`);
        setRunning(false); stopStream();
      }
    } catch (e) {
      setErr((e as Error).message); setRunning(false); stopStream();
    }
  };

  const stop = async () => {
    await fetch(`/api/tasks/${taskId}/interrupt`, { method: "POST" }).catch(() => {});
    setRunning(false); stopStream();
  };

  useEffect(() => () => stopStream(), [taskId]);

  return (
    <div className="flex h-full flex-col bg-bg">
      <div ref={scrollRef} className="scroll-thin flex-1 overflow-y-auto overflow-x-hidden px-6 py-5">
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          <AssistantBubble>
            我是 Builder 智能体。已收到资产 <Badge tone="accent">{task.asset_slug || "custom"}</Badge>。描述你希望生成的 Agent 具备的能力，或直接让我开始分析资产并构建。
          </AssistantBubble>
          {messages.map((m) => (
            <MsgBubble key={m.id} m={m} />
          ))}
        </div>
      </div>

      {err && <div className="mx-auto w-full max-w-2xl px-6"><div className="mb-2 rounded-xl border border-err/20 bg-err-weak px-3 py-2 text-sm text-err">{err}</div></div>}

      {/* Floating composer over the unified center background */}
      <div className="shrink-0 bg-bg px-4 pb-4 pt-2">
        <div className="mx-auto flex max-w-2xl items-end gap-2 rounded-2xl border border-border-soft bg-white p-2 shadow-soft">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="描述你的需求，Enter 发送，Shift+Enter 换行"
            rows={1}
            className="scroll-thin max-h-40 flex-1 resize-none overflow-y-auto overflow-x-hidden bg-transparent px-2 py-1.5 text-sm text-ink outline-none placeholder:text-subink"
          />
          {running ? (
            <button onClick={stop} className="flex items-center gap-1.5 rounded-lg border border-border-soft px-3 py-2 text-sm text-subink transition hover:bg-surface-2">
              <Stop size={14} weight="fill" /> 停止
            </button>
          ) : (
            <button onClick={send} disabled={!value.trim()} className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-soft-sm transition hover:opacity-90 disabled:opacity-40">
              <PaperPlaneRight size={14} weight="fill" /> 发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function AssistantBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ok text-white shadow-soft-sm"><Robot size={16} weight="fill" /></div>
      <div className="break-words rounded-2xl rounded-tl-none bg-surface-2 px-4 py-3 text-sm leading-relaxed text-ink">{children}</div>
    </div>
  );
}

function MsgBubble({ m }: { m: UiMessage }) {
  if (m.role === "user") {
    return (
      <div className="flex items-start justify-end gap-3">
        <div className="break-words rounded-2xl rounded-tr-none bg-primary px-4 py-3 text-sm leading-relaxed text-white">{m.content}</div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ok text-white shadow-soft-sm"><Robot size={16} weight="fill" /></div>
      <div className="min-w-0 flex-1">
        {m.content && <div className="whitespace-pre-wrap break-words rounded-2xl rounded-tl-none bg-surface-2 px-4 py-3 text-sm leading-relaxed text-ink">{m.content}</div>}
        {m.tool_cards.length > 0 && (
          <div className="mt-2 space-y-2">
            {m.tool_cards.map((c) => <ToolCardView key={c.id} card={c} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCardView({ card }: { card: ToolCard }) {
  const [open, setOpen] = useState(false);
  const tone = card.status === "running" ? "accent" : card.status === "error" ? "err" : "ok";
  return (
    <div className="rounded-xl border border-border-soft bg-white shadow-soft-sm">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        <TerminalWindow size={14} className="shrink-0 text-subink" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{card.name}</span>
        {card.status === "running" ? <CircleNotch size={14} className="m2a-spin shrink-0 text-accent" /> :
          card.status === "error" ? <XCircle size={14} weight="fill" className="shrink-0 text-err" /> :
            <CheckCircle size={14} weight="fill" className="shrink-0 text-ok" />}
        <span className={cn("text-xs font-medium", tone === "err" ? "text-err" : tone === "ok" ? "text-ok" : "text-accent")}>
          {card.status === "running" ? "运行中" : card.status === "error" ? "失败" : "完成"}
        </span>
      </button>
      {open && (
        <div className="border-t border-border-soft px-3 py-2 text-xs text-subink">
          {card.input && <div className="mb-1"><span className="font-medium text-ink">输入</span><pre className="mt-1 overflow-x-hidden whitespace-pre-wrap break-words rounded-lg bg-[#FAF9F8] p-2">{card.input}</pre></div>}
          {card.result && <div><span className="font-medium text-ink">结果</span><pre className="mt-1 max-h-60 overflow-y-auto overflow-x-hidden whitespace-pre-wrap break-words rounded-lg bg-[#FAF9F8] p-2">{card.result}</pre></div>}
        </div>
      )}
    </div>
  );
}
