import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Robot, User, Hexagon, ChatCircle, CaretDoubleLeft, CaretDoubleRight,
} from "@phosphor-icons/react";
import type { AgentConfig, ChatMessage, Conversation, RunResult, ToolCard, Uploaded } from "./types";
import { fetchConfig, fetchApiDocs, listConversations, createConversation, deleteConversation,
         conversationMessages, streamChat, upload, interrupt } from "./api";
import type { ApiDoc } from "./types";
import ConversationList from "./components/ConversationList";
import Composer from "./components/Composer";
import ResultCard from "./components/ResultCard";
import ProcessVisualizer from "./components/ProcessVisualizer";
import ApiDocs from "./components/ApiDocs";
import ToolCards from "./components/ToolCards";

let _mid = 0;
const mid = () => `m${++_mid}`;

export default function App() {
  const [cfg, setCfg] = useState<AgentConfig | null>(null);
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [cid, setCid] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [results, setResults] = useState<{ id: string; run: RunResult; attachment: Uploaded | null }[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [attachment, setAttachment] = useState<Uploaded | null>(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"result" | "trace" | "apidocs">("result");
  const [apidoc, setApidoc] = useState<ApiDoc | null>(null);
  const [apidocErr, setApidocErr] = useState("");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [rightW, setRightW] = useState(400);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; w: number } | null>(null);

  const ui = cfg?.agent_ui ?? null;
  const presets = ui?.presets ?? [];

  useEffect(() => {
    fetchConfig().then(setCfg).catch((e) => setErr(String(e)));
    fetchApiDocs().then(setApidoc).catch((e) => setApidocErr(String(e)));
    listConversations().then(setConvos).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, running]);

  // Responsive three-pane: collapse side panes when embedded in a narrow iframe
  // (e.g. the Builder preview) so the composer is never overlapped.
  // Depends on cfg: the root div only exists after the config has loaded.
  useEffect(() => {
    const el = rootRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const apply = () => {
      const w = el.clientWidth;
      if (!w) return;
      if (w < 760) { setLeftOpen(false); setRightOpen(false); }
      else if (w < 980) { setLeftOpen(false); setRightOpen(true); }
      else { setLeftOpen(true); setRightOpen(true); }
    };
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    apply();
    return () => ro.disconnect();
  }, [cfg]);

  const ensureCid = useCallback(async (): Promise<string> => {
    if (cid) return cid;
    const c = await createConversation();
    setCid(c.id);
    setConvos((prev) => [c, ...prev]);
    return c.id;
  }, [cid]);

  const loadMessages = useCallback(async (cidv: string) => {
    try {
      const r = await conversationMessages(cidv);
      setMessages(r.messages.map((m) => ({ ...m, streaming: false })));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (cid) loadMessages(cid);
  }, [cid, loadMessages]);

  async function selectConversation(c: Conversation) {
    setCid(c.id);
    setAttachment(null);
    setResults([]);
    setErr("");
    await loadMessages(c.id);
  }

  async function newConversation() {
    const c = await createConversation();
    setConvos((prev) => [c, ...prev]);
    setCid(c.id);
    setMessages([]);
    setResults([]);
    setAttachment(null);
  }

  async function removeConversation(c: Conversation) {
    await deleteConversation(c.id);
    setConvos((prev) => prev.filter((x) => x.id !== c.id));
    if (cid === c.id) { setCid(null); setMessages([]); setResults([]); }
  }

  async function onUpload(f: File) {
    setUploading(true);
    setErr("");
    try {
      const id = await ensureCid();
      const u = await upload(f, id);
      setAttachment(u);
    } catch (e) {
      setErr(String(e));
    } finally {
      setUploading(false);
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || running || !cfg) return;
    setInput("");
    setErr("");
    const id = await ensureCid().catch((e) => { setErr(String(e)); return null; });
    if (!id) return;
    setRunning(true);

    const userMsg: ChatMessage = { id: mid(), role: "user", content: text, attachment };
    const aMsg: ChatMessage = { id: mid(), role: "assistant", content: "", cards: [], streaming: true };
    setMessages((m) => [...m, userMsg, aMsg]);
    setAttachment(null);

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((all) => all.map((m) => (m.id === aMsg.id ? fn(m) : m)));

    try {
      await streamChat(id, text, userMsg.attachment ?? null, (ev) => {
        if (ev.type === "text_delta") {
          patch((m) => ({ ...m, content: m.content + (ev.text || "") }));
        } else if (ev.type === "tool_started") {
          patch((m) => ({
            ...m,
            cards: [...(m.cards || []), { id: ev.card_id || mid(), name: ev.name || "tool", status: "running", input: ev.input } as ToolCard],
          }));
        } else if (ev.type === "tool_completed" || ev.type === "tool_failed") {
          patch((m) => ({
            ...m,
            cards: (m.cards || []).map((c) =>
              c.id === ev.card_id ? { ...c, status: ev.type === "tool_failed" ? "error" : "done", result: String(ev.result ?? "") } : c,
            ),
          }));
        } else if (ev.type === "model_run") {
          const run: RunResult = { capability: ev.capability || "predict", result: ev.result, trace: (ev.trace as RunResult["trace"]) || undefined };
          setResults((prev) => [...prev, { id: mid(), run, attachment: userMsg.attachment ?? null }]);
          patch((m) => ({ ...m, capability: run.capability }));
        } else if (ev.type === "run_completed") {
          patch((m) => ({ ...m, streaming: false, error: !!ev.is_error }));
          listConversations().then(setConvos).catch(() => {});
        } else if (ev.type === "run_failed") {
          patch((m) => ({ ...m, streaming: false, error: true, content: m.content || ev.text || "运行失败" }));
        }
      });
    } catch (e) {
      patch((m) => ({ ...m, streaming: false, error: true, content: m.content || String(e) }));
      setErr(String(e));
    } finally {
      patch((m) => ({ ...m, streaming: false }));
      setRunning(false);
    }
  }

  async function stop() {
    try { if (cid) await interrupt(cid); } catch { /* ignore */ }
    setRunning(false);
  }

  // ---- right panel drag ----
  const onResizeDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current = { x: e.clientX, w: rightW };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onResizeMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return;
    const max = Math.min(760, Math.max(320, window.innerWidth - 480));
    setRightW(Math.max(320, Math.min(max, dragRef.current.w - (e.clientX - dragRef.current.x))));
  };
  const onResizeUp = () => { dragRef.current = null; };

  if (!cfg) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-subink">
        {err ? <span className="text-err">{err}</span> : "加载模型配置…"}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="flex h-full w-full overflow-hidden bg-bg">
      {/* left: conversation list */}
      <div className={`shrink-0 transition-all ${leftOpen ? "w-64" : "w-12"}`}>
        {leftOpen ? (
          <ConversationList
            conversations={convos}
            activeId={cid}
            onSelect={selectConversation}
            onCreate={newConversation}
            onDelete={removeConversation}
          />
        ) : (
          <div className="flex h-full flex-col items-center gap-2 bg-surface-2 py-3" style={{ borderRight: "1px solid var(--color-border-soft)" }}>
            <button onClick={() => setLeftOpen(true)} title="展开会话" className="text-subink hover:text-accent">
              <CaretDoubleRight size={16} />
            </button>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-white" title="新建会话" onClick={newConversation}>
              <ChatCircle size={15} />
            </div>
          </div>
        )}
      </div>

      {/* center: chat + composer */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header cfg={cfg} />
        <div ref={scrollRef} className="scroll-thin flex-1 overflow-y-auto px-4 py-4">
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {messages.length === 0 && (
              <div className="m2a-fade py-14 text-center">
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-weak text-accent"><Robot size={26} /></div>
                <div className="text-base font-semibold text-ink">{cfg.slug} 模型 Agent</div>
                <div className="mt-1 text-sm text-subink">真实权重推理 · 能力：{cfg.capabilities.join(" / ")}</div>
              </div>
            )}
            {messages.map((m) => <MessageRow key={m.id} m={m} />)}
            {running && messages[messages.length - 1]?.content === "" && !(messages[messages.length - 1]?.cards?.length) && (
              <div className="flex items-center gap-1 px-1 text-xs text-subink">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.2s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.1s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
              </div>
            )}
          </div>
        </div>
        <Composer
          ui={ui ?? { model: { slug: cfg.slug, framework: cfg.framework, input_type: cfg.input_type, labels: cfg.labels, capabilities: cfg.capabilities, vector_len: cfg.vector_len, feature_names: cfg.feature_names }, input: { mode: cfg.input_type, feature_names: cfg.feature_names, sample: null, dim: cfg.vector_len }, presets, pipeline: ["input", "preprocess", "features", "inference", "result"], result_views: cfg.capabilities }}
          attachment={attachment}
          onUpload={onUpload}
          onAttachmentChange={setAttachment}
          presets={presets}
          value={input}
          onValueChange={setInput}
          onSend={send}
          running={running}
          uploading={uploading}
          onStop={stop}
          error={err}
        />
      </div>

      {/* draggable divider */}
      {rightOpen && (
        <div
          role="separator"
          aria-orientation="vertical"
          onPointerDown={onResizeDown}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeUp}
          className="w-1 cursor-col-resize bg-transparent transition hover:bg-accent/30"
        />
      )}

      {/* right: results / trace / api docs */}
      {rightOpen && (
        <div className="flex shrink-0 flex-col border-l bg-bg" style={{ borderColor: "var(--color-border-soft)", width: rightW }}>
          <div className="flex items-center gap-1 border-b px-2 py-2" style={{ borderColor: "var(--color-border-soft)" }}>
            <TabBtn active={tab === "result"} onClick={() => setTab("result")}>结果{results.length ? ` (${results.length})` : ""}</TabBtn>
            <TabBtn active={tab === "trace"} onClick={() => setTab("trace")}>执行轨迹</TabBtn>
            <TabBtn active={tab === "apidocs"} onClick={() => setTab("apidocs")}>API 文档</TabBtn>
            <button onClick={() => setRightOpen(false)} className="ml-auto p-1 text-subink hover:text-accent" title="收起"><CaretDoubleLeft size={15} /></button>
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {tab === "result" && (
              results.length === 0 ? (
                <div className="p-4 text-center text-xs text-subink">还没有推理结果。放入输入并提问，结果会出现在这里。</div>
              ) : (
                <div className="space-y-2 p-3">
                  {results.map((r) => <ResultCard key={r.id} run={r.run} cfg={cfg} />)}
                </div>
              )
            )}
            {tab === "trace" && (
              results.length === 0 ? (
                <div className="p-4 text-center text-xs text-subink">运行一次推理后，这里展示真实执行轨迹。</div>
              ) : (
                <div className="p-3">
                  <ProcessVisualizer ui={ui ?? { model: { slug: cfg.slug, framework: cfg.framework, input_type: cfg.input_type, labels: cfg.labels, capabilities: cfg.capabilities, vector_len: cfg.vector_len, feature_names: cfg.feature_names }, input: { mode: cfg.input_type, feature_names: cfg.feature_names, sample: null, dim: cfg.vector_len }, presets, pipeline: ["input", "preprocess", "features", "inference", "result"], result_views: cfg.capabilities }} run={results[results.length - 1]?.run ?? null} attachment={results[results.length - 1]?.attachment ?? attachment} />
                </div>
              )
            )}
            {tab === "apidocs" && <ApiDocs doc={apidoc} err={apidocErr} />}
          </div>
        </div>
      )}

      {!rightOpen && (
        <button
          onClick={() => setRightOpen(true)}
          className="absolute right-2 top-1/2 z-40 -translate-y-1/2 rounded-lg border border-border-soft bg-white p-1.5 text-subink shadow-soft-sm hover:text-accent"
          title="展开右侧面板"
        >
          <CaretDoubleLeft size={15} />
        </button>
      )}
    </div>
  );
}

function Header({ cfg }: { cfg: AgentConfig }) {
  return (
    <div className="shrink-0 border-b" style={{ borderColor: "var(--color-border-soft)" }}>
      <div className="flex items-center gap-2.5 px-4 py-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ok text-white shadow-soft-sm"><Hexagon size={17} weight="fill" /></div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold" data-testid="gen-slug">{cfg.slug}</div>
          <div className="truncate text-[11px] text-subink">{cfg.model_id} · {cfg.framework} · {cfg.input_type}</div>
        </div>
        <div className="ml-auto flex flex-wrap justify-end gap-1">
          {cfg.capabilities.map((c) => (
            <span key={c} className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-subink">{c}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="rounded-lg px-3 py-1 text-sm font-medium transition"
      style={active ? { background: "var(--color-accent-weak)", color: "var(--color-accent)" } : { color: "var(--color-subink)" }}
    >
      {children}
    </button>
  );
}

function MessageRow({ m }: { m: ChatMessage }) {
  const isUser = m.role === "user";
  return (
    <div className={`m2a-fade flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
        style={{ background: isUser ? "var(--color-surface-2)" : "var(--color-accent-weak)" }}
      >
        {isUser ? <User size={14} color="#8E8E8E" /> : <Robot size={14} style={{ color: "var(--color-accent)" }} />}
      </div>
      <div className={`min-w-0 max-w-[85%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block rounded-2xl px-3 py-2 text-sm ${isUser ? "" : "w-full"}`}
          style={isUser ? { background: "var(--color-surface-2)" } : { background: "transparent" }}
        >
          {m.content ? (
            <div className="md break-words text-left text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            </div>
          ) : m.streaming ? (
            <span className="text-xs text-subink">思考中…</span>
          ) : null}
          {m.error && <div className="mt-1 text-xs text-err">（本轮出错）</div>}
          {m.cards && m.cards.length > 0 && <ToolCards cards={m.cards} />}
        </div>
      </div>
    </div>
  );
}
