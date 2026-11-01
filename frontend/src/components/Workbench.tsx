// Center panel: multi-turn chat with the Builder Agent (real SSE stream).
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PaperPlaneRight, Stop, Robot, TerminalWindow, CheckCircle, XCircle, CircleNotch, CaretRight } from "@phosphor-icons/react";
import type { Task, ToolCard, SseEvent } from "../types";
import { api } from "../lib/api";
import { EventStream } from "../lib/sse";
import { cn, Badge } from "./ui";
import { RunTimeline, type StageRow } from "./RunTimeline";

interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;       // final answer (text after the last tool call; or the whole text when no tools)
  process_text: string;  // execution narration frozen at tool boundaries
  thinking: string;      // real thinking blocks (ephemeral, not persisted)
  tool_cards: ToolCard[];
  stages: StageRow[];
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
          process_text: "", thinking: "",
          tool_cards: m.tool_cards || [], stages: [], streaming: false,
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
    const mid = `a-${e.run_id}`;
    if (e.type === "run_started") {
      setRunning(true); setErr("");
      setMessages((prev) => [...prev, { id: mid, role: "assistant", content: "", process_text: "", thinking: "", tool_cards: [], stages: [], streaming: true }]);
    } else if (e.type === "thinking_delta") {
      setMessages((prev) => prev.map((m) => (m.id === mid ? { ...m, thinking: m.thinking + e.text } : m)));
    } else if (e.type === "text_delta") {
      setMessages((prev) => prev.map((m) => (m.id === mid ? { ...m, content: m.content + e.text } : m)));
    } else if (e.type === "tool_started" || e.type === "tool_completed" || e.type === "tool_failed") {
      setMessages((prev) => prev.map((m) => {
        if (m.id !== mid) return m;
        const cards = [...m.tool_cards];
        const i = cards.findIndex((c) => c.id === e.card_id);
        const card: ToolCard = { id: e.card_id, name: e.name, status: e.status as ToolCard["status"], input: e.input, result: (e as any).result ?? "" };
        if (i >= 0) cards[i] = card; else cards.push(card);
        // First sighting of a tool: any text streamed so far is execution
        // narration, so freeze it into process_text and start a fresh answer.
        const firstSeen = e.type === "tool_started" && i < 0;
        return {
          ...m, tool_cards: cards,
          process_text: firstSeen ? m.process_text + m.content : m.process_text,
          content: firstSeen ? "" : m.content,
        };
      }));
    } else if (e.type === "run_stage") {
      setMessages((prev) => prev.map((m) => {
        if (m.id !== mid) return m;
        const rows = [...m.stages];
        const row: StageRow = { stage: e.stage, status: e.status, tool: e.tool, round: e.round, evidence: e.evidence };
        const i = rows.findIndex((r) => r.stage === e.stage && r.round === e.round);
        if (i >= 0) rows[i] = row; else rows.push(row);
        return { ...m, stages: rows };
      }));
    } else if (e.type === "run_completed" || e.type === "run_failed") {
      setRunning(false);
      setMessages((prev) => prev.map((m) => {
        if (m.id !== mid) return m;
        // If the run ended right after a tool with no trailing answer text, fall
        // back to the narration so the final reply is never blank.
        const fallback = !m.content.trim() && m.process_text.trim() !== "";
        return { ...m, streaming: false, content: fallback ? m.process_text : m.content, process_text: fallback ? "" : m.process_text };
      }));
      stopStream();
    } else if (e.type === "run_cancelled") {
      setRunning(false);
      setMessages((prev) => prev.map((m) => {
        if (m.id !== mid) return m;
        return {
          ...m, streaming: false,
          tool_cards: m.tool_cards.map((c) => (c.status === "running" ? { ...c, status: "error", result: "运行已取消" } : c)),
        };
      }));
      stopStream();
    }
  };

  const send = async () => {
    if (!value.trim() || running) return;
    const text = value.trim();
    setValue("");
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", content: text, process_text: "", thinking: "", tool_cards: [], stages: [], streaming: false }]);
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
        {m.content && (
          <div className="md break-words rounded-2xl rounded-tl-none bg-surface-2 px-4 py-3 text-sm leading-relaxed text-ink">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          </div>
        )}
        <ProcessPanel cards={m.tool_cards} stages={m.stages} thinking={m.thinking} processText={m.process_text} streaming={m.streaming} />
      </div>
    </div>
  );
}

// One collapsible panel gathering the agent's execution (tool calls) + thinking
// for this assistant turn. Expanded while streaming, auto-collapsed once the run
// ends; the final answer stays in the bubble above.
function ProcessPanel({ cards, stages, thinking, processText, streaming }: {
  cards: ToolCard[]; stages: StageRow[]; thinking: string; processText: string; streaming: boolean;
}) {
  // Hooks must run before any early return.
  const [open, setOpen] = useState(streaming);
  const prevStreaming = useRef(streaming);
  useEffect(() => {
    // Collapse only on the live true -> false transition, never on every render,
    // so a manual toggle is not overridden.
    if (prevStreaming.current && !streaming) setOpen(false);
    prevStreaming.current = streaming;
  }, [streaming]);

  const hasThinking = thinking.trim().length > 0;
  const hasProcess = processText.trim().length > 0;
  if (cards.length === 0 && !hasThinking && !hasProcess && stages.length === 0) return null;

  const failed = cards.filter((c) => c.status === "error").length;
  const active = streaming || cards.some((c) => c.status === "running");
  const statusLabel = failed > 0 ? `${failed} 失败` : active ? "运行中" : "已完成";
  const statusTone = failed > 0 ? "text-err" : active ? "text-accent" : "text-ok";

  return (
    <div className="mt-2 rounded-2xl border border-border-soft bg-white shadow-soft-sm">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        <TerminalWindow size={14} className="shrink-0 text-subink" />
        <span className="text-sm font-medium text-ink">执行过程</span>
        {cards.length > 0 && <span className="text-xs text-subink">· {cards.length} 步</span>}
        {active ? <CircleNotch size={14} className="m2a-spin shrink-0 text-accent" /> :
          failed > 0 ? <XCircle size={14} weight="fill" className="shrink-0 text-err" /> :
            <CheckCircle size={14} weight="fill" className="shrink-0 text-ok" />}
        <span className={cn("text-xs font-medium", statusTone)}>{statusLabel}</span>
        <CaretRight size={14} className={cn("ml-auto shrink-0 text-subink transition", open && "rotate-90")} />
      </button>
      {open && (
        <div className="border-t border-border-soft px-3 py-2">
          {hasThinking && (
            <div className="mb-2">
              <div className="mb-1 text-xs font-medium text-ink">思考</div>
              <pre className="max-h-60 overflow-y-auto overflow-x-hidden whitespace-pre-wrap break-words rounded-lg bg-[#FAF9F8] p-2 text-xs text-subink">{thinking}</pre>
            </div>
          )}
          {hasProcess && (
            <div className="mb-2 whitespace-pre-wrap break-words text-xs text-subink">{processText}</div>
          )}
          {stages.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 text-xs font-medium text-ink">执行轨迹</div>
              <RunTimeline stages={stages} />
            </div>
          )}
          {cards.length > 0 && (
            <div className="space-y-2">
              {cards.map((c) => <ToolCardView key={c.id} card={c} />)}
            </div>
          )}
        </div>
      )}
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
