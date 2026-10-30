import { useState } from "react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { ToolCard } from "../types";

export default function ToolCards({ cards }: { cards: ToolCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="mt-2 space-y-1.5">
      {cards.map((c) => (
        <ToolRow key={c.id} card={c} />
      ))}
    </div>
  );
}

function ToolRow({ card }: { card: ToolCard }) {
  const [open, setOpen] = useState(false);
  const running = card.status === "running";
  const err = card.status === "error";
  return (
    <div
      className="m2a-fade rounded-lg border px-2.5 py-1.5 text-xs"
      style={{
        borderColor: err ? "var(--color-err)" : "var(--color-border)",
        background: err ? "#fef2f2" : "var(--color-surface)",
      }}
    >
      <div className="flex items-center gap-2">
        {running ? (
          <Loader2 size={13} className="animate-spin" style={{ color: "var(--color-subink)" }} />
        ) : err ? (
          <XCircle size={13} style={{ color: "var(--color-err)" }} />
        ) : (
          <CheckCircle2 size={13} style={{ color: "var(--color-ok)" }} />
        )}
        <span className="font-medium">{card.name}</span>
        <span className="text-[var(--color-subink)]">
          {running ? "运行中" : err ? "失败" : "完成"}
        </span>
        {card.result && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="ml-auto text-[var(--color-accent)] hover:underline"
          >
            {open ? "收起" : "详情"}
          </button>
        )}
      </div>
      {open && card.result && (
        <pre className="m-0 mt-1.5 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-[#0f172a] p-2 text-[11px] text-[#e2e8f0]">
          {card.result}
        </pre>
      )}
    </div>
  );
}
