/** Real Builder execution timeline. Rows come from genuine run_stage SSE events;
 *  never fabricated. Shows the production stages and rewrite iterations. */
import { useMemo } from "react";
import { CheckCircle, XCircle, CircleNotch, ArrowsClockwise } from "@phosphor-icons/react";

export interface StageRow {
  stage: string;
  status: string; // running | done | error
  tool: string;
  round: number;
  evidence: string;
}

export function RunTimeline({ stages }: { stages: StageRow[] }) {
  const groups = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, StageRow[]>();
    for (const s of stages) {
      if (!map.has(s.stage)) {
        map.set(s.stage, []);
        order.push(s.stage);
      }
      map.get(s.stage)!.push(s);
    }
    return order.map((k) => ({ stage: k, rows: map.get(k)! }));
  }, [stages]);

  return (
    <div className="space-y-1.5">
      {groups.map((g) => {
        const last = g.rows[g.rows.length - 1];
        const failed = g.rows.some((r) => r.status === "error");
        const active = g.rows.some((r) => r.status === "running");
        const tone = failed ? "text-err" : active ? "text-accent" : "text-ok";
        const Icon = failed ? XCircle : active ? CircleNotch : CheckCircle;
        const iter = g.rows.length > 1 ? (
          <span className="ml-1 inline-flex items-center gap-0.5 text-[10px] text-subink">
            <ArrowsClockwise size={11} /> ×{g.rows.length}
          </span>
        ) : null;
        return (
          <div key={g.stage} className="rounded-lg border border-border-soft bg-white px-2.5 py-1.5">
            <div className="flex items-center gap-1.5 text-xs">
              <Icon size={13} weight="fill" className={tone === "text-ok" ? "text-ok" : tone === "text-err" ? "text-err" : "m2a-spin text-accent"} />
              <span className="font-medium text-ink">{g.stage}</span>
              {iter}
              <span className={`ml-auto font-medium ${tone}`}>
                {failed ? "失败" : active ? "运行中" : "完成"}
              </span>
            </div>
            {last.evidence && (
              <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-1.5 text-[10px] text-subink">
                {last.evidence}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}
