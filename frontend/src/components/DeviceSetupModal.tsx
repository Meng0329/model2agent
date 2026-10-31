// One-time device setup modal (auto-opens on first new-task if not configured).
import { useEffect, useState } from "react";
import { Cpu, CheckCircle, X } from "@phosphor-icons/react";
import { useTasks } from "../state/TasksProvider";
import { cn, Spinner } from "./ui";
import type { DeviceInfo } from "../types";

export function DeviceSetupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { devices, device, deviceConfigured, selectDevice } = useTasks();
  const [sel, setSel] = useState<string>(device || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (open) setSel(device || "");
  }, [open, device]);

  if (!open) return null;

  const save = async () => {
    setErr("");
    if (!sel) return setErr("请选择运行设备");
    setBusy(true);
    try {
      await selectDevice(sel);
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm">
      <div className="m2a-fade w-full max-w-lg rounded-2xl border border-border-soft bg-white p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-weak text-accent">
              <Cpu size={17} weight="duotone" />
            </span>
            配置运行设备
          </div>
          {deviceConfigured && (
            <button onClick={onClose} className="rounded-lg p-1 text-subink transition hover:bg-surface-2"><X size={18} /></button>
          )}
        </div>
        <p className="mt-2 text-sm text-subink">选择 Builder 与生成 Agent 实际使用的设备（CPU 或某块 GPU）。</p>

        <div className="mt-4 space-y-2.5">
          {devices.map((d: DeviceInfo, i: number) => (
            <DeviceRow
              key={d.id}
              d={d}
              selected={sel === d.id}
              recommended={d.kind === "gpu" && i === 0}
              onSelect={() => setSel(d.id)}
            />
          ))}
        </div>

        {err && <div className="mt-3 rounded-xl border border-err/20 bg-err-weak px-3 py-2 text-sm text-err">{err}</div>}

        <div className="mt-5 flex justify-end gap-2">
          {deviceConfigured && <button onClick={onClose} className="rounded-lg border border-border-soft px-4 py-2 text-sm text-subink transition hover:bg-surface-2">取消</button>}
          <button
            onClick={save}
            disabled={busy}
            className={cn("flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-white shadow-soft-sm transition hover:opacity-90", busy && "opacity-70")}
          >
            {busy && <Spinner />} 保存
          </button>
        </div>
      </div>
    </div>
  );
}

function DeviceRow({ d, selected, recommended, onSelect }: { d: DeviceInfo; selected: boolean; recommended?: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "relative flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left transition",
        selected ? "border-2 border-accent bg-accent-soft" : "border border-border-soft bg-surface-2 hover:border-accent/50"
      )}
    >
      <span
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border bg-white",
          selected ? "border-4 border-accent" : "border-border"
        )}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-ink">{d.label}</span>
        <span className="text-xs text-subink">
          {d.kind === "gpu" ? `可用显存 ${d.free_gb ?? "?"} GB / ${d.total_gb ?? "?"} GB` : "CPU · 无显存"}
        </span>
      </span>
      {recommended && !selected && (
        <span className="absolute right-3 top-3 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-white">推荐</span>
      )}
      {selected && <CheckCircle size={18} weight="fill" className="shrink-0 text-accent" />}
    </button>
  );
}
