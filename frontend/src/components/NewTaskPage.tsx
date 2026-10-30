// New-task form: name, goal, asset upload (ZIP or multi-file). Asset required.
import { useState } from "react";
import { UploadCloud, File as FileIcon, X, Cpu, AlertCircle } from "lucide-react";
import { useTasks } from "../state/TasksProvider";
import { cn, Spinner } from "./ui";

export function NewTaskPage({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
  const { createTask, device, deviceConfigured } = useTasks();
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list).filter((f) => !prev.some((p) => p.name === f.name))]);
  };

  const submit = async () => {
    setErr("");
    if (!name.trim()) return setErr("请填写任务名称");
    if (files.length === 0) return setErr("请上传模型资产（ZIP 或多文件）");
    if (!deviceConfigured) return setErr("请先配置运行设备");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("name", name.trim());
      form.append("goal", goal.trim());
      form.append("device", device);
      files.forEach((f) => form.append("files", f, f.name));
      await createTask(form);
      onCreated();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center overflow-y-auto bg-surface p-6">
      <div className="w-full max-w-xl rounded-2xl border border-border bg-white p-7 m2a-fade">
        <h2 className="text-lg font-semibold text-ink">新建任务</h2>
        <p className="mt-1 text-sm text-subink">上传训练好的模型资产，Builder 智能体将自主分析并生成专属 Agent。</p>

        <div className="mt-5 space-y-4">
          <Field label="任务名称" required>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：手写数字图片分类 Agent"
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <Field label="任务目标">
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="希望生成的 Agent 能做什么？例如：上传一张图片，返回数字分类与置信度。"
              rows={3}
              className="w-full resize-none rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <Field label="模型资产" required>
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border bg-surface px-4 py-6 text-center transition hover:border-accent">
              <UploadCloud size={26} className="text-accent" />
              <span className="text-sm text-ink">点击或拖入 ZIP / 多文件</span>
              <span className="text-xs text-subink">支持 .zip 压缩包或分开的 manifest.json / infer.py / 权重 / 示例</span>
              <input type="file" multiple className="hidden" onChange={(e) => addFiles(e.target.files)} />
            </label>
            {files.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {files.map((f, i) => (
                  <div key={f.name} className="flex items-center gap-2 rounded-md border border-border bg-white px-2.5 py-1.5 text-sm">
                    <FileIcon size={14} className="shrink-0 text-subink" />
                    <span className="min-w-0 flex-1 truncate">{f.name}</span>
                    <span className="shrink-0 text-xs text-subink">{(f.size / 1024).toFixed(1)} KB</span>
                    <button onClick={() => setFiles((p) => p.filter((_, j) => j !== i))} className="shrink-0 rounded p-0.5 text-subink hover:text-err">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Field>

          <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
            <Cpu size={15} className="text-accent" />
            <span className="text-subink">运行设备</span>
            <span className="ml-auto font-medium text-ink">{device || "未配置"}</span>
          </div>

          {err && (
            <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-err">
              <AlertCircle size={15} /> {err}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button onClick={onCancel} className="rounded-lg border border-border px-4 py-2 text-sm text-subink hover:bg-surface">取消</button>
            <button
              onClick={submit}
              disabled={busy}
              className={cn("flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white transition hover:bg-teal-700", busy && "opacity-70")}
            >
              {busy && <Spinner />} 创建并开始
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-ink">
        {label} {required && <span className="text-err">*</span>}
      </label>
      {children}
    </div>
  );
}
