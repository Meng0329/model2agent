import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Robot, PaperPlaneRight, Stop, Hexagon, User } from "@phosphor-icons/react";
import type { AgentConfig, ChatMessage, RunResult, ToolCard, Uploaded } from "./types";
import { fetchConfig, interrupt, newSid, streamChat } from "./api";
import UploadPanel from "./components/UploadPanel";
import ToolCards from "./components/ToolCards";
import ResultCard from "./components/ResultCard";

let _mid = 0;
const mid = () => `m${++_mid}`;

export default function App() {
  const [cfg, setCfg] = useState<AgentConfig | null>(null);
  const [err, setErr] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [results, setResults] = useState<{ id: string; run: RunResult }[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [attachment, setAttachment] = useState<Uploaded | null>(null);
  const sid = useMemo(() => newSid(), []);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchConfig()
      .then(setCfg)
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, results, running]);

  async function send() {
    const text = input.trim();
    if (!text || running || !cfg) return;
    setInput("");
    setErr("");
    setRunning(true);

    const userMsg: ChatMessage = { id: mid(), role: "user", content: text };
    const aMsg: ChatMessage = { id: mid(), role: "assistant", content: "", cards: [], streaming: true };
    setMessages((m) => [...m, userMsg, aMsg]);

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((all) => all.map((m) => (m.id === aMsg.id ? fn(m) : m)));

    try {
      await streamChat(sid, text, attachment, (ev) => {
        if (ev.type === "text_delta") {
          patch((m) => ({ ...m, content: m.content + (ev.text || "") }));
        } else if (ev.type === "tool_started") {
          patch((m) => ({
            ...m,
            cards: [...(m.cards || []), { id: ev.card_id || mid(), name: ev.name || "tool", status: "running", input: ev.input }],
          }));
        } else if (ev.type === "tool_completed" || ev.type === "tool_failed") {
          patch((m) => ({
            ...m,
            cards: (m.cards || []).map((c) =>
              c.id === ev.card_id
                ? { ...c, status: ev.type === "tool_failed" ? "error" : "done", result: ev.result }
                : c,
            ),
          }));
        } else if (ev.type === "run_completed") {
          patch((m) => ({ ...m, streaming: false, error: !!ev.is_error }));
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
    try {
      await interrupt(sid);
    } catch {
      /* ignore */
    }
  }

  function onResult(run: RunResult) {
    setResults((r) => [...r, { id: mid(), run }]);
  }

  const [tab, setTab] = useState<"chat" | "result">("chat");

  if (!cfg) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-subink">
        {err ? <span className="text-err">{err}</span> : "加载模型配置…"}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" style={{ background: "var(--color-bg)" }}>
      <Header cfg={cfg} />
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden px-4">
        <div className="flex shrink-0 items-center gap-1 border-b pb-2 pt-2" style={{ borderColor: "var(--color-border-soft)" }}>
          <TabBtn active={tab === "chat"} onClick={() => setTab("chat")}>对话</TabBtn>
          <TabBtn active={tab === "result"} onClick={() => setTab("result")}>
            推理结果{results.length ? ` (${results.length})` : ""}
          </TabBtn>
        </div>

        {tab === "chat" ? (
          <ChatArea
            messages={messages}
            results={results}
            running={running}
            scrollRef={scrollRef}
            onSuggestion={(s) => setInput(s)}
            cfg={cfg}
          />
        ) : (
          <div ref={scrollRef} className="flex-1 overflow-auto py-3">
            {results.length === 0 ? (
              <div className="py-16 text-center text-sm text-subink">还没有推理结果。上传图片/CSV 后点击「预测」。</div>
            ) : (
              results.map((r) => (
                <div key={r.id} className="mb-2">
                  <ResultCard run={r.run} cfg={cfg} />
                </div>
              ))
            )}
          </div>
        )}

        <div className="shrink-0 border-t py-3" style={{ borderColor: "var(--color-border-soft)" }}>
          {err && <div className="mb-2 rounded-md border border-err/20 bg-err-weak px-2 py-1 text-xs text-err">{err}</div>}
          <UploadPanel cfg={cfg} sid={sid} onUploaded={setAttachment} onResult={onResult} />
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={
                attachment
                  ? "就上传的数据提问，例如：这是什么？为什么？"
                  : "输入问题，或先上传数据…"
              }
              rows={1}
              data-testid="gen-chat-input"
              className="max-h-32 min-h-[42px] flex-1 resize-none rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none transition placeholder:text-subink focus:border-accent"
            />
            {running ? (
              <button
                onClick={stop}
                className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl text-white shadow-soft-sm transition hover:opacity-90"
                style={{ background: "var(--color-err)" }}
                title="停止"
                data-testid="gen-stop"
              >
                <Stop size={16} weight="fill" />
              </button>
            ) : (
              <button
                onClick={send}
                disabled={!input.trim()}
                className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl text-white shadow-soft-sm transition hover:opacity-90 disabled:opacity-40"
                style={{ background: "var(--color-primary)" }}
                title="发送"
                data-testid="gen-send"
              >
                <PaperPlaneRight size={17} weight="fill" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Header({ cfg }: { cfg: AgentConfig }) {
  return (
    <div className="shrink-0 border-b" style={{ borderColor: "var(--color-border-soft)" }}>
      <div className="mx-auto flex w-full max-w-3xl items-center gap-2.5 px-4 py-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ok text-white shadow-soft-sm">
          <Hexagon size={17} weight="fill" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold" data-testid="gen-slug">{cfg.slug}</div>
          <div className="truncate text-[11px] text-subink">
            {cfg.model_id} · {cfg.framework} · {cfg.input_type}
          </div>
        </div>
        <div className="ml-auto flex flex-wrap justify-end gap-1">
          {cfg.capabilities.map((c) => (
            <span key={c} className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-subink">
              {c}
            </span>
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

function ChatArea({
  messages,
  results,
  running,
  scrollRef,
  onSuggestion,
  cfg,
}: {
  messages: ChatMessage[];
  results: { id: string; run: RunResult }[];
  running: boolean;
  scrollRef: React.RefObject<HTMLDivElement>;
  onSuggestion: (s: string) => void;
  cfg: AgentConfig;
}) {
  const empty = messages.length === 0 && results.length === 0;
  const suggestions = suggestionsFor(cfg);
  return (
    <div ref={scrollRef} className="flex-1 overflow-auto py-3">
      {empty && (
        <div className="m2a-fade py-10 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-weak text-accent">
            <Robot size={26} />
          </div>
          <div className="text-base font-semibold text-ink">{cfg.slug} 模型 Agent</div>
          <div className="mt-1 text-sm text-subink">
            真实权重推理 · 能力：{cfg.capabilities.join(" / ")}
          </div>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSuggestion(s)}
                className="rounded-full border border-border-soft bg-white px-3 py-1.5 text-xs text-subink shadow-soft-sm transition hover:border-accent hover:text-accent"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
      {messages.map((m) => (
        <MessageRow key={m.id} m={m} cfg={cfg} />
      ))}
      {running && messages[messages.length - 1]?.content === "" && !(messages[messages.length - 1]?.cards?.length) && (
        <div className="flex items-center gap-1 px-1 text-xs text-subink">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
        </div>
      )}
    </div>
  );
}

function suggestionsFor(cfg: AgentConfig): string[] {
  if (cfg.input_type === "image") {
    return ["上传一张图片后问：这是什么数字？", "解释模型的预测依据", "这个模型的输入是什么？"];
  }
  if (cfg.input_type === "tabular") {
    return ["上传 CSV 后问：这批样本的预测结果？", "哪些特征最重要？", "这个模型的准确率如何？"];
  }
  return ["这个模型能做什么？", "描述一下你的能力", "如何输入数据？"];
}

function MessageRow({ m, cfg }: { m: ChatMessage; cfg: AgentConfig }) {
  const isUser = m.role === "user";
  return (
    <div className={`m2a-fade mb-3 flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
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
