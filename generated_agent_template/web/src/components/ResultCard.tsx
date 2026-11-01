import { Pulse, ChartBar, Lightbulb, ListBullets, Hash } from "@phosphor-icons/react";
import type { AgentConfig, RunResult } from "../types";

/** Renders the REAL output of /api/model/run without fabricating anything. */
export default function ResultCard({ run, cfg }: { run: RunResult; cfg: AgentConfig }) {
  const r = run.result;

  const labelName = (k: string | number) => {
    const i = Number(k);
    if (Number.isFinite(i) && cfg.labels && cfg.labels[i] !== undefined) return `${cfg.labels[i]}`;
    return String(k);
  };

  if (run.capability === "predict") {
    const val = typeof r === "number" ? r : Number((r as { [k: string]: unknown })?.predict ?? r);
    const name = cfg.labels && Number.isFinite(Number(val)) && cfg.labels[Number(val)] !== undefined
      ? cfg.labels[Number(val)]
      : null;
    return (
      <Card icon={<Hash size={15} weight="bold" />} title="预测结果">
        <div className="flex items-end gap-2">
          <span className="text-3xl font-bold text-accent">
            {Number.isFinite(Number(val)) ? Number(val) : String(val)}
          </span>
          {name != null && <span className="pb-1 text-sm text-subink">＝ {name}</span>}
        </div>
      </Card>
    );
  }

  if (run.capability === "predict_proba" && r && typeof r === "object") {
    const entries = Object.entries(r as Record<string, number>).sort((a, b) => b[1] - a[1]);
    return (
      <Card icon={<ChartBar size={15} />} title="类别概率">
        <div className="space-y-1.5">
          {entries.map(([k, p]) => (
            <Bar key={k} label={labelName(k)} value={p} />
          ))}
        </div>
      </Card>
    );
  }

  if (run.capability === "saliency" && Array.isArray(r)) {
    const rows = r as { pixel: number; grad: number }[];
    const max = Math.max(1e-9, ...rows.map((x) => Math.abs(x.grad)));
    return (
      <Card icon={<Pulse size={15} />} title={`像素显著性 Top-${rows.length}`}>
        <div className="space-y-1">
          {rows.map((x) => (
            <div key={x.pixel} className="flex items-center gap-2 text-xs">
              <span className="w-16 shrink-0 font-mono text-subink">px #{x.pixel}</span>
              <div className="h-3 flex-1 rounded bg-surface-2">
                <div
                  className="h-3 rounded"
                  style={{
                    width: `${(Math.abs(x.grad) / max) * 100}%`,
                    background: x.grad >= 0 ? "var(--color-accent)" : "var(--color-err)",
                  }}
                />
              </div>
              <span className="w-16 shrink-0 text-right font-mono text-ink">{x.grad.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (run.capability === "explain" && Array.isArray(r)) {
    const rows = r as { feature: string; gain?: number; importance?: number }[];
    const val = (x: { gain?: number; importance?: number }) => x.gain ?? x.importance ?? 0;
    const max = Math.max(1e-9, ...rows.map((x) => Math.abs(val(x))));
    return (
      <Card icon={<Lightbulb size={15} />} title={`特征重要性 Top-${rows.length}`}>
        <div className="space-y-1">
          {rows.map((x) => (
            <div key={x.feature} className="flex items-center gap-2 text-xs">
              <span className="w-36 shrink-0 truncate text-subink" title={x.feature}>{x.feature}</span>
              <div className="h-3 flex-1 rounded bg-surface-2">
                <div className="h-3 rounded" style={{ width: `${(Math.abs(val(x)) / max) * 100}%`, background: "var(--color-accent)" }} />
              </div>
              <span className="w-20 shrink-0 text-right font-mono text-ink">{val(x).toFixed(3)}</span>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (run.capability === "classes" && Array.isArray(r)) {
    return (
      <Card icon={<ListBullets size={15} />} title="类别">
        <div className="flex flex-wrap gap-1.5">
          {(r as unknown[]).map((c, i) => (
            <span key={i} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs font-medium text-ink">
              {labelName(c as string | number)}
            </span>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card icon={<Pulse size={15} />} title={`结果 · ${run.capability}`}>
      <pre className="m-0 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-2 p-2 text-xs text-ink">
        {JSON.stringify(r, null, 2)}
      </pre>
    </Card>
  );
}

function Card({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="m2a-fade rounded-xl border border-border-soft bg-white p-3 shadow-soft-sm">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-subink">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 font-medium text-ink">{label}</span>
      <div className="h-3 flex-1 rounded bg-surface-2">
        <div className="h-3 rounded" style={{ width: `${Math.min(100, value * 100)}%`, background: "var(--color-accent)" }} />
      </div>
      <span className="w-12 shrink-0 text-right font-mono text-ink">{(value * 100).toFixed(1)}%</span>
    </div>
  );
}
