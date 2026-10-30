import { useRef, useState } from "react";
import { Image as ImageIcon, FileSpreadsheet, Type, SlidersHorizontal, Play, Loader2, X, Upload } from "lucide-react";
import type { AgentConfig, RunResult, Uploaded } from "../types";
import { runModel, upload } from "../api";

interface Props {
  cfg: AgentConfig;
  sid: string;
  onUploaded: (u: Uploaded) => void;
  onResult: (run: RunResult) => void;
}

/** Input widget driven by config.json input_type — never hard-coded to one model. */
export default function UploadPanel({ cfg, sid, onUploaded, onResult }: Props) {
  if (cfg.input_type === "image") return <ImageUpload cfg={cfg} sid={sid} onUploaded={onUploaded} onResult={onResult} />;
  if (cfg.input_type === "tabular") return <CsvUpload cfg={cfg} sid={sid} onUploaded={onUploaded} onResult={onResult} />;
  if (cfg.input_type === "text") return <TextInput onUploaded={onUploaded} />;
  return <VectorInput cfg={cfg} sid={sid} onUploaded={onUploaded} onResult={onResult} />;
}

function useUploader() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  return { busy, setBusy, err, setErr };
}

function PanelWrap({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2 rounded-xl border bg-[var(--color-surface)] p-3" style={{ borderColor: "var(--color-border)" }}>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-subink)]">{title}</div>
      {children}
    </div>
  );
}

function ImageUpload({ cfg, sid, onUploaded, onResult }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [feats, setFeats] = useState<number[] | null>(null);
  const [vlen, setVlen] = useState<number | null>(null);
  const { busy, setBusy, err, setErr } = useUploader();
  const cap = cfg.default_capability || "predict";

  async function onFile(f: File) {
    setErr("");
    setPreview(URL.createObjectURL(f));
    setFileName(f.name);
    setBusy(true);
    try {
      const u = (await upload(f, sid)) as Extract<Uploaded, { input_type: "image" }>;
      setFeats(u.features);
      setVlen(u.vector_len);
      onUploaded(u);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function predict() {
    if (!feats) return;
    setErr("");
    setBusy(true);
    try {
      const r = await runModel(cap, { features: feats });
      onResult(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PanelWrap title="输入 · 图片">
      <div className="flex items-center gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border-2 border-dashed text-[var(--color-subink)]"
          style={{ borderColor: "var(--color-border)" }}
          data-testid="gen-upload"
        >
          {preview ? <img src={preview} alt="preview" className="h-full w-full object-contain" /> : <ImageIcon size={22} />}
        </button>
        <div className="min-w-0 flex-1 text-xs text-[var(--color-subink)]">
          {fileName ? (
            <div className="flex items-center gap-2">
              <span className="truncate">{fileName}</span>
              <span className="rounded bg-[var(--color-accent-weak)] px-1.5 py-0.5 font-medium text-[var(--color-accent)]">
                {feats ? `${vlen} 维特征就绪` : "解析中…"}
              </span>
            </div>
          ) : (
            <div>点击或拖拽上传图片，模型将缩放到 {cfg.vector_len ?? 64} 维特征输入。</div>
          )}
          {err && <div className="mt-1 text-[var(--color-err)]">{err}</div>}
        </div>
        {feats && (
          <button
            onClick={predict}
            disabled={busy}
            className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--color-accent)" }}
            data-testid="gen-run"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            预测
          </button>
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
    </PanelWrap>
  );
}

function CsvUpload({ cfg, sid, onUploaded, onResult }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("");
  const [rows, setRows] = useState<{ features: number[]; row: Record<string, string> }[] | null>(null);
  const [batch, setBatch] = useState<{ row: number; pred: number }[] | null>(null);
  const { busy, setBusy, err, setErr } = useUploader();
  const cap = cfg.default_capability || "predict";

  async function onFile(f: File) {
    setErr("");
    setFileName(f.name);
    setBatch(null);
    setBusy(true);
    try {
      const u = (await upload(f, sid)) as Extract<Uploaded, { input_type: "tabular" }>;
      setRows(u.rows);
      onUploaded(u);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function batchPredict() {
    if (!rows) return;
    setErr("");
    setBusy(true);
    try {
      const out: { row: number; pred: number }[] = [];
      for (let i = 0; i < rows.length; i++) {
        const r = await runModel(cap, { features: rows[i].features });
        out.push({ row: i + 1, pred: Number((r.result as { predict?: number } | number) ?? r.result) });
        if (i === 0) onResult(r); // first row shown as a rich card
      }
      setBatch(out);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const ncols = cfg.vector_len ?? rows?.[0]?.features.length ?? null;

  return (
    <PanelWrap title="输入 · CSV">
      <div className="flex items-center gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex h-12 shrink-0 items-center gap-2 rounded-lg border-2 border-dashed px-3 text-xs text-[var(--color-subink)]"
          style={{ borderColor: "var(--color-border)" }}
          data-testid="gen-upload"
        >
          <FileSpreadsheet size={16} />
          {fileName || "选择 CSV"}
        </button>
        <div className="min-w-0 flex-1 text-xs text-[var(--color-subink)]">
          {rows ? (
            <span>
              <span className="rounded bg-[var(--color-accent-weak)] px-1.5 py-0.5 font-medium text-[var(--color-accent)]">
                {rows.length} 行 × {ncols} 列
              </span>{" "}
              · 按 feature_names 排序列
            </span>
          ) : (
            <span>上传 CSV，每行为一个样本。</span>
          )}
          {err && <div className="mt-1 text-[var(--color-err)]">{err}</div>}
        </div>
        {rows && (
          <button
            onClick={batchPredict}
            disabled={busy}
            className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--color-accent)" }}
            data-testid="gen-run"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            批量预测
          </button>
        )}
      </div>
      {batch && (
        <div className="mt-2 max-h-40 overflow-auto rounded-lg border text-xs" style={{ borderColor: "var(--color-border)" }}>
          <table className="w-full">
            <thead className="sticky top-0 bg-[var(--color-surface-2)]">
              <tr>
                <th className="px-2 py-1 text-left">行</th>
                <th className="px-2 py-1 text-left">预测</th>
              </tr>
            </thead>
            <tbody>
              {batch.map((b) => (
                <tr key={b.row}>
                  <td className="px-2 py-1">{b.row}</td>
                  <td className="px-2 py-1 font-mono">{b.pred}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
    </PanelWrap>
  );
}

function TextInput({ onUploaded }: { onUploaded: (u: Uploaded) => void }) {
  const [text, setText] = useState("");
  return (
    <PanelWrap title="输入 · 文本">
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onUploaded({ input_type: "text", text: e.target.value });
        }}
        placeholder="输入文本…"
        rows={2}
        className="w-full resize-none rounded-lg border p-2 text-sm outline-none focus:border-[var(--color-accent)]"
        style={{ borderColor: "var(--color-border)" }}
        data-testid="gen-text"
      />
    </PanelWrap>
  );
}

function VectorInput({ cfg, onUploaded, onResult }: Props) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [feats, setFeats] = useState<number[] | null>(null);
  const { busy, setBusy, err, setErr } = useUploader();
  const cap = cfg.default_capability || "predict";

  function parse() {
    const parts = text.replace(/,/g, " ").split(/\s+/).filter(Boolean).map(Number);
    if (parts.length === cfg.vector_len) {
      setFeats(parts);
      onUploaded({ input_type: "vector", features: parts });
      setErr("");
    } else {
      setErr(`需要 ${cfg.vector_len} 个数字（当前 ${parts.length}）`);
    }
  }

  async function predict() {
    if (!feats) return;
    setBusy(true);
    try {
      const r = await runModel(cap, { features: feats });
      onResult(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <PanelWrap title="输入 · 向量">
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 text-xs text-[var(--color-accent)] hover:underline"
        >
          <SlidersHorizontal size={13} /> 高级：直接输入 {cfg.vector_len} 维特征向量
        </button>
      </PanelWrap>
    );
  }

  return (
    <PanelWrap title="输入 · 向量">
      <div className="flex items-start gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`${cfg.vector_len} 个逗号/空格分隔的数字`}
          rows={2}
          className="w-full resize-none rounded-lg border p-2 font-mono text-xs outline-none focus:border-[var(--color-accent)]"
          style={{ borderColor: "var(--color-border)" }}
        />
        <button
          onClick={parse}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-white"
          style={{ background: "var(--color-accent)" }}
        >
          应用
        </button>
        {feats && (
          <button onClick={predict} disabled={busy} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--color-accent)" }} data-testid="gen-run">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            预测
          </button>
        )}
      </div>
      {err && <div className="mt-1 text-xs text-[var(--color-err)]">{err}</div>}
    </PanelWrap>
  );
}
