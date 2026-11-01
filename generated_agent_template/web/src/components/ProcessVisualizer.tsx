import { Hash, Image as ImageIcon, ChartBar, Cpu, Lightning } from "@phosphor-icons/react";
import type { AgentUi, RunResult, Uploaded } from "../types";

interface Props {
  ui: AgentUi;
  run: RunResult | null;
  attachment: Uploaded | null;
}

/** AI2UI: render the REAL execution trace of one model run, per the asset's
 *  declared pipeline. Every number shown comes from real weights. */
export default function ProcessVisualizer({ ui, run, attachment }: Props) {
  const trace = run?.trace ?? attachment?.trace ?? null;
  const stages = ui.pipeline ?? [];
  const grid = trace?.grid ?? null;
  const cap = run?.capability ?? trace?.capability ?? null;

  return (
    <div className="space-y-2">
      {stages.includes("input") && (
        <Stage icon={<Lightning size={14} />} title="输入">
          <div className="text-xs text-subink">
            {attachment ? describeInput(attachment) : "尚未提供输入"}
          </div>
        </Stage>
      )}
      {stages.includes("preprocess") && (
        <Stage icon={<ImageIcon size={14} />} title="预处理">
          {grid ? (
            <div className="flex items-center gap-3">
              <ImageGrid grid={grid} />
              <div className="text-[11px] text-subink">
                <div>画布 {grid.length}×{grid[0]?.length ?? 0}</div>
                <div>极性 {trace?.input_type === "image" ? "ink_on_dark" : "—"}</div>
                {attachment?.trace?.bbox && <div>包围盒 {JSON.stringify(attachment.trace.bbox)}</div>}
              </div>
            </div>
          ) : (
            <div className="text-xs text-subink">无预处理数据</div>
          )}
        </Stage>
      )}
      {stages.includes("features") && (
        <Stage icon={<Hash size={14} />} title="特征">
          <div className="text-xs text-subink">
            {trace?.features ? `${trace.features.length} 维` : attachment?.features ? `${attachment.features.length} 维特征` : "—"}
          </div>
        </Stage>
      )}
      {stages.includes("inference") && (
        <Stage icon={<Cpu size={14} />} title="推理">
          <div className="text-xs text-subink">
            {cap ? `capability=${cap}` : "未执行"}{trace?.latency_ms != null ? ` · ${trace.latency_ms}ms` : ""}
          </div>
        </Stage>
      )}
      {stages.includes("result") && run && (
        <Stage icon={<ChartBar size={14} />} title="结果">
          <pre className="m-0 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-2 p-2 text-[11px] text-ink">
            {JSON.stringify(run.result, null, 2)}
          </pre>
        </Stage>
      )}
    </div>
  );
}

function describeInput(a: Uploaded): string {
  if (a.input_type === "image") return `图片 → ${a.vector_len ?? ""} 维特征`;
  if (a.input_type === "tabular") return `CSV ${a.rows?.length ?? 0} 行`;
  if (a.input_type === "vector") return `${a.features?.length ?? 0} 维向量`;
  if (a.input_type === "text") return `文本 ${(a.text ?? "").length} 字`;
  return a.input_type;
}

export function ImageGrid({ grid }: { grid: number[][] }) {
  const n = grid.length;
  const max = Math.max(1e-9, ...grid.flat().map((v) => Math.abs(v)));
  return (
    <div className="inline-grid gap-px rounded-lg border border-border-soft bg-white p-1" style={{ gridTemplateColumns: `repeat(${n}, minmax(0,1fr))` }}>
      {grid.flat().map((v, i) => {
        const a = Math.min(1, Math.abs(v) / max);
        return (
          <div
            key={i}
            className="h-4 w-4"
            style={{ background: `rgba(214,162,146,${a})` }}
            title={String(v)}
          />
        );
      })}
    </div>
  );
}

function Stage({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border-soft bg-white p-3 shadow-soft-sm">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-subink">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}
