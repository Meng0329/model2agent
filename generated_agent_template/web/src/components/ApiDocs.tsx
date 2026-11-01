import { useState } from "react";
import { Copy, Check, ArrowSquareOut } from "@phosphor-icons/react";
import type { ApiDoc, ApiEndpoint } from "../types";

const LANGS = ["curl", "python", "javascript"] as const;
type Lang = typeof LANGS[number];

export default function ApiDocs({ doc, err }: { doc: ApiDoc | null; err: string }) {
  if (err) return <div className="p-4 text-xs text-err">{err}</div>;
  if (!doc) return <div className="p-4 text-xs text-subink">加载 API 文档…</div>;
  return (
    <div className="space-y-3 p-4">
      <div>
        <div className="text-sm font-semibold text-ink">{doc.title}</div>
        <div className="mt-0.5 text-[11px] text-subink">
          {doc.model?.slug} · {doc.model?.framework} · {doc.model?.input_type}
        </div>
        <a
          href={doc.swagger}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:underline"
        >
          <ArrowSquareOut size={13} /> 打开 Swagger /docs
        </a>
      </div>
      {doc.endpoints.map((e) => <Endpoint key={`${e.method} ${e.path}`} e={e} />)}
      {doc.sse_events?.length > 0 && (
        <div className="rounded-xl border border-border-soft bg-surface-2 p-3">
          <div className="mb-1 text-xs font-semibold text-ink">SSE 事件</div>
          <div className="flex flex-wrap gap-1">
            {doc.sse_events.map((s) => (
              <span key={s} className="rounded bg-white px-1.5 py-0.5 font-mono text-[10px] text-subink">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Endpoint({ e }: { e: ApiEndpoint }) {
  const [lang, setLang] = useState<Lang>("curl");
  const [copied, setCopied] = useState(false);
  const snippet = e.snippets?.[lang];
  const tone = e.method === "GET" ? "text-ok" : e.method === "DELETE" ? "text-err" : "text-accent";
  return (
    <div className="rounded-xl border border-border-soft bg-white p-3 shadow-soft-sm">
      <div className="flex items-center gap-2">
        <span className={`font-mono text-[11px] font-bold ${tone}`}>{e.method}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">{e.path}</span>
      </div>
      <div className="mt-1 text-[11px] text-subink">{e.summary}</div>
      {e.request != null && (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-2 p-2 text-[10px] text-ink">
          {typeof e.request === "string" ? e.request : JSON.stringify(e.request, null, 2)}
        </pre>
      )}
      {snippet && (
        <div className="mt-2">
          <div className="mb-1 flex items-center gap-1">
            {LANGS.map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className="rounded px-1.5 py-0.5 text-[10px] font-medium transition"
                style={l === lang ? { background: "var(--color-accent-weak)", color: "var(--color-accent)" } : { color: "var(--color-subink)" }}
              >
                {l}
              </button>
            ))}
            <button
              onClick={async () => { await navigator.clipboard?.writeText(snippet); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
              className="ml-auto flex items-center gap-1 text-[10px] text-subink hover:text-accent"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? "已复制" : "复制"}
            </button>
          </div>
          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-primary p-2 text-[10px] text-[#E8E4E1]">{snippet}</pre>
        </div>
      )}
    </div>
  );
}
