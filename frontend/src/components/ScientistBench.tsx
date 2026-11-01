// Model-to-Scientist benchmark dashboard (read-only).
// Shows the frozen S1 grid and the real run ledger; NOT_TESTED cells stay empty.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ArrowsClockwise, CheckCircle, CircleNotch, XCircle, MinusCircle, X } from "@phosphor-icons/react";
import { api } from "../lib/api";
import { Badge, cn } from "./ui";
import type {
  ScientistBenchmark, ScientistCell, ScientistRun, ScientistRunDetail,
} from "../types";

const METHODS = ["B0", "B1", "B2", "B3", "M"];
const METHOD_DESC: Record<string, string> = {
  B0: "通用 LLM（无模型工具）",
  B1: "LLM + 模型工具",
  B2: "直接合成（可写代码）",
  B3: "通用科研脚手架",
  M: "完整 SMSC（生成式科学家）",
};

function pct(v: number | null | undefined) {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}
function usd(v: number | null | undefined) {
  return v == null ? "—" : `$${v.toFixed(2)}`;
}

function StatusDot({ cell }: { cell?: ScientistCell }) {
  if (!cell || cell.status === "NOT_TESTED") {
    return <MinusCircle size={16} className="text-subink/40" weight="duotone" />;
  }
  return cell.status === "OBSERVED"
    ? <CheckCircle size={16} className="text-ok" weight="fill" />
    : <XCircle size={16} className="text-err" weight="fill" />;
}

export function ScientistBench({ onExit }: { onExit?: () => void }) {
  const [bench, setBench] = useState<ScientistBenchmark | null>(null);
  const [runs, setRuns] = useState<ScientistRun[]>([]);
  const [detail, setDetail] = useState<ScientistRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ task: string; method: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, r] = await Promise.all([api.scientistBenchmark(), api.scientistRuns()]);
      setBench(b);
      setRuns(r.runs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // load on mount, poll, and refresh when the tab becomes visible again
  useEffect(() => {
    load();
    const id = window.setInterval(load, 20000);
    const onVis = () => { if (document.visibilityState === "visible") load(); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("focus", onVis);
    };
  }, [load]);

  const latestRun = useMemo(() => {
    const map = new Map<string, ScientistRun>();
    for (const r of runs) {
      const key = `${r.scientific_task_id}::${r.method_id}`;
      const cur = map.get(key);
      // prefer non-harness runs; otherwise keep the newest
      if (!cur || (cur.failure_category?.startsWith("harness_") && !r.failure_category?.startsWith("harness_"))) {
        map.set(key, r);
      }
    }
    return map;
  }, [runs]);

  const openCell = async (task: string, method: string) => {
    const run = latestRun.get(`${task}::${method}`);
    if (!run) return;
    setSelected({ task, method });
    setDetail(null);
    try {
      setDetail(await api.scientistRun(run.run_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-subink">
        <CircleNotch size={18} className="animate-spin" /> 加载基准…
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      {/* header */}
      <div className="flex items-center justify-between border-b border-border-soft bg-white px-5 py-3">
        <div>
          <div className="text-sm font-semibold text-ink">Model-to-Scientist 基准</div>
          <div className="mt-0.5 text-xs text-subink">
            {bench?.tasks.length ?? 0} 个冻结任务 · {bench?.n_runs ?? 0} 条真实运行
            {bench?.n_harness_runs ? ` · ${bench.n_harness_runs} 条 harness 缺陷运行（不计入）` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="flex items-center gap-1.5 rounded-lg border border-border-soft px-2.5 py-1.5 text-xs text-subink transition hover:bg-surface-2"
            title="刷新"
          >
            <ArrowsClockwise size={14} /> 刷新
          </button>
          {onExit && (
            <button onClick={onExit} className="rounded-lg border border-border-soft px-2.5 py-1.5 text-xs text-subink hover:bg-surface-2">
              返回 Builder
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mx-5 mt-4 rounded-xl border border-err/30 bg-err-weak px-4 py-3 text-sm text-err">
          {error}（数据来自本地 ledger；若后端刚重启请稍后刷新）
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto p-5">
        {/* method summary */}
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {METHODS.map((m) => {
            const s = bench?.by_method?.[m];
            return (
              <div key={m} className={cn(
                "rounded-2xl border bg-white p-4 shadow-soft-sm",
                m === "M" ? "border-accent-border" : "border-border-soft",
              )}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-ink">{m}</span>
                  {s?.status === "NOT_TESTED"
                    ? <Badge>未运行</Badge>
                    : s?.status === "OBSERVED"
                      ? <Badge tone="ok">SISR {pct(s?.sisr_rate)}</Badge>
                      : <Badge tone="err">SISR {pct(s?.sisr_rate)}</Badge>}
                </div>
                <div className="mt-1 text-[11px] leading-4 text-subink">{METHOD_DESC[m]}</div>
                <div className="mt-3 flex items-center justify-between text-xs text-subink">
                  <span>n={s?.n ?? 0}</span>
                  <span>SEV {s?.mean_sev == null ? "—" : s.mean_sev.toFixed(2)}</span>
                  <span>{usd(s?.mean_cost_usd ?? null)}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* grid */}
        <div className="overflow-hidden rounded-2xl border border-border-soft bg-white shadow-soft">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border-soft bg-surface-2/60 text-left text-xs text-subink">
                <th className="px-4 py-2.5 font-medium">任务</th>
                <th className="px-3 py-2.5 font-medium">难度</th>
                {METHODS.map((m) => (
                  <th key={m} className="px-3 py-2.5 text-center font-medium">{m}</th>
                ))}
                <th className="px-3 py-2.5 text-right font-medium">方法明细</th>
              </tr>
            </thead>
            <tbody>
              {bench?.tasks.map((t) => (
                <tr key={t.task_id} className="border-b border-border-soft/70 last:border-0 hover:bg-surface-2/30">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">{t.task_id}</div>
                    <div className="mt-0.5 text-xs text-subink">{t.domain} · {t.split}</div>
                  </td>
                  <td className="px-3 py-3">
                    <Badge tone="accent">{t.capability_level}</Badge>
                  </td>
                  {METHODS.map((m) => {
                    const c = bench.cells?.[t.task_id]?.[m];
                    const run = latestRun.get(`${t.task_id}::${m}`);
                    return (
                      <td key={m} className="px-3 py-3 text-center">
                        <button
                          disabled={!run}
                          onClick={() => openCell(t.task_id, m)}
                          className={cn(
                            "inline-flex min-w-[86px] items-center justify-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition",
                            run ? "cursor-pointer hover:bg-surface-2" : "cursor-default",
                            c?.status === "OBSERVED" ? "border-ok/30 bg-ok-weak text-ok"
                              : c?.status === "FAILED" ? "border-err/30 bg-err-weak text-err"
                                : "border-border-soft bg-white text-subink/60",
                          )}
                          title={run ? `${run.run_id} · ${usd(run.cost)}` : "NOT_TESTED"}
                        >
                          <StatusDot cell={c} />
                          {c?.status === "NOT_TESTED" || !c ? "未运行" : pct(c.sisr_rate)}
                        </button>
                      </td>
                    );
                  })}
                  <td className="px-3 py-3 text-right text-xs text-subink">
                    {METHODS.map((m) => {
                      const c = bench.cells?.[t.task_id]?.[m];
                      return c?.n ? `${m}:${c.n}` : null;
                    }).filter(Boolean).join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 rounded-xl border border-border-soft bg-white px-4 py-3 text-xs leading-5 text-subink">
          <b className="text-ink">读法：</b>SISR = 预注册成功判据 ∧ 真实模型调用 &gt; 0 ∧ 有效证据 ∧ 产物齐全；
          NOT_TESTED 表示该（任务, 方法）本轮未运行，不是失败。SEV 只统计引用可解析到证据 ledger 的结论。
          每次运行的证据、结论、最终选择与 oracle 访问日志都可点开查看。
        </div>
      </div>

      {/* detail drawer */}
      {selected && (
        <RunDrawer
          title={`${selected.task} · ${selected.method}`}
          detail={detail}
          onClose={() => { setSelected(null); setDetail(null); }}
        />
      )}
    </div>
  );
}

function RunDrawer({ title, detail, onClose }: {
  title: string; detail: ScientistRunDetail | null; onClose: () => void;
}) {
  const run = detail?.run ?? {};
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/20" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-xl flex-col border-l border-border-soft bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border-soft px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-ink">{title}</div>
            <div className="truncate text-xs text-subink">{String(run.run_id ?? "")}</div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-subink hover:bg-surface-2"><X size={16} /></button>
        </div>

        {!detail ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-subink">
            <CircleNotch size={16} className="animate-spin" /> 加载运行详情…
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-auto p-4 text-sm">
            {detail.harness_artifact_note && (
              <div className="mb-3 rounded-lg border border-err/30 bg-err-weak px-3 py-2 text-xs text-err">
                {detail.harness_artifact_note}
              </div>
            )}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <Meta label="状态" value={run.scientific_task_success ? "OBSERVED（SISR 成功）" : "FAILED"} />
              <Meta label="oracle" value={run.final_conclusion_validity ? "命中" : "未命中"} />
              <Meta label="SEV" value={run.evidence_validity == null ? "—" : String(run.evidence_validity)} />
              <Meta label="假设修订" value={run.adaptation_success ? "有" : "无"} />
              <Meta label="模型调用" value={String(run.model_call_count ?? "—")} />
              <Meta label="oracle 查询" value={String(run.experiment_count ?? detail.oracle_queries ?? "—")} />
              <Meta label="成本" value={usd((run.cost as number) ?? null)} />
              <Meta label="时延" value={run.latency == null ? "—" : `${Math.round(Number(run.latency))} s`} />
              <Meta label="生成状态" value={String(run.agent_generation_status ?? "—")} />
              <Meta label="失败类别" value={String(run.failure_category ?? "—")} />
            </dl>

            {detail.final_selection?.top_ids?.length ? (
              <Section title="最终选择（final_selection.json）">
                <div className="flex flex-wrap gap-1.5">
                  {detail.final_selection.top_ids.map((id, i) => (
                    <span key={id} className="rounded-md border border-border-soft bg-surface-2 px-2 py-0.5 text-xs text-ink">
                      {i + 1}. {id}
                    </span>
                  ))}
                </div>
              </Section>
            ) : (
              <Section title="最终选择"><span className="text-xs text-err">未写出 final_selection.json</span></Section>
            )}

            {detail.conclusions.length > 0 && (
              <Section title={`结论（${detail.conclusions.length}）`}>
                <div className="space-y-2">
                  {detail.conclusions.map((c, i) => {
                    const text = (c.statement || c.claim || c.conclusion || "") as string;
                    const ids = (c.supporting_evidence || c.supporting_records || c.evidence_ids || c.evidence || []) as unknown[];
                    return (
                      <div key={i} className="rounded-lg border border-border-soft bg-surface-2/40 p-2.5">
                        <div className="text-xs leading-5 text-ink">{String(text)}</div>
                        {Array.isArray(ids) && ids.length > 0 && (
                          <div className="mt-1 text-[11px] text-subink">引用：{ids.map(String).join(", ")}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}

            {detail.revisions.length > 0 && (
              <Section title={`假设修订（${detail.revisions.length}）`}>
                <div className="space-y-1.5">
                  {detail.revisions.map((r, i) => (
                    <div key={i} className="rounded-lg border border-border-soft p-2 text-xs">
                      <span className="font-medium text-ink">{String(r.hypothesis_id ?? "")}</span>
                      <span className="text-subink"> → {String(r.revision ?? "")}</span>
                      {r.reason ? <div className="mt-0.5 text-[11px] text-subink">{String(r.reason)}</div> : null}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            <Section title={`证据 ledger（${detail.evidence.length}）`}>
              <div className="max-h-48 overflow-auto rounded-lg border border-border-soft">
                <table className="w-full text-[11px]">
                  <thead className="bg-surface-2 text-subink">
                    <tr><th className="px-2 py-1 text-left">id</th><th className="px-2 py-1 text-left">类型</th><th className="px-2 py-1 text-left">观察</th></tr>
                  </thead>
                  <tbody>
                    {detail.evidence.map((e, i) => (
                      <tr key={i} className="border-t border-border-soft/60">
                        <td className="px-2 py-1 text-subink">{String(e.id ?? "")}</td>
                        <td className="px-2 py-1"><Badge tone="accent">{String(e.evidence_type ?? "")}</Badge></td>
                        <td className="px-2 py-1 text-ink">{String(e.observed_result ?? e.observation ?? "").slice(0, 160)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-subink">{label}</dt>
      <dd className="mt-0.5 font-medium text-ink">{value}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-4">
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-subink">{title}</div>
      {children}
    </div>
  );
}
