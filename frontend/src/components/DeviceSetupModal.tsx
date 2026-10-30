// One-time device setup modal (auto-opens on first new-task if not configured).
import { useEffect, useState } from "react";
import { Cpu, CheckCircle2, X } from "lucide-react";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-white p-6 m2a-fade">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Cpu size={18} className="text-accent" /> 配置运行设备
          </div>
          {deviceConfigured && (
            <button onClick={onClose} className="rounded p-1 text-subink hover:bg-surface"><X size={18} /></button>
          )}
        </div>
        <p className="mt-1 text-sm text-subink">选择 Builder 与生成 Agent 实际使用的设备（CPU 或某块 GPU）。</p>

        <div className="mt-4 space-y-2">
          {devices.map((d: DeviceInfo) => (
            <DeviceRow key={d.id} d={d} selected={sel === d.id} onSelect={() => setSel(d.id)} />
          ))}
        </div>

        {err && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-err">{err}</div>}

        <div className="mt-5 flex justify-end gap-2">
          {deviceConfigured && <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-subink hover:bg-surface">取消</button>}
          <button
            onClick={save}
            disabled={busy}
            className={cn("flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white transition hover:bg-teal-700", busy && "opacity-70")}
          >
            {busy && <Spinner />} 保存
          </button>
        </div>
      </div>
    </div>
  );
}

function DeviceRow({ d, selected, onSelect }: { d: DeviceInfo; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition",
        selected ? "border-accent bg-teal-50" : "border-border bg-white hover:border-accent/50"
      )}
    >
      <Cpu size={18} className={selected ? "text-accent" : "text-subink"} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-ink">{d.label}</div>
        <div className="text-xs text-subink">
          {d.kind === "gpu" ? `可用显存 ${d.free_gb ?? "?"} GB / ${d.total_gb ?? "?"} GB` : "CPU · 无显存"}
        </div>
      </div>
      {selected && <CheckCircle2 size={18} className="text-accent" />}
    </button>
  );
}
