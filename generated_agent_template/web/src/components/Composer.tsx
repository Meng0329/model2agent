import { useRef, useState } from "react";
import {
  PaperPlaneRight, Stop, CircleNotch, UploadSimple, Table, X, Sliders,
} from "@phosphor-icons/react";
import type { AgentUi, AgentUiInput, Uploaded } from "../types";

interface Props {
  ui: AgentUi;
  attachment: Uploaded | null;
  onUpload: (f: File) => Promise<void>;
  onAttachmentChange: (u: Uploaded | null) => void;
  presets: string[];
  value: string;
  onValueChange: (v: string) => void;
  onSend: () => void;
  running: boolean;
  uploading: boolean;
  onStop: () => void;
  error: string;
}

/** Per-model input fused with the text composer. The agent produces the output —
 *  there is deliberately no standalone "predict" button. */
export default function Composer(p: Props) {
  const input = p.ui.input;
  return (
    <div className="shrink-0 px-4 pb-4 pt-2">
      <div className="mx-auto flex max-w-3xl flex-col gap-2 rounded-2xl border border-border-soft bg-white p-2 shadow-soft">
        <InputControl {...p} input={input} />
        <div className="flex items-end gap-2">
          <textarea
            value={p.value}
            onChange={(e) => p.onValueChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                p.onSend();
              }
            }}
            placeholder={
              p.attachment
                ? "就这份输入提问，或点选下方预设问题…"
                : "描述你的问题，或先放入该模型需要的输入…"
            }
            rows={1}
            data-testid="gen-chat-input"
            className="scroll-thin max-h-36 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-1.5 text-sm text-ink outline-none placeholder:text-subink"
          />
          {p.running ? (
            <button
              onClick={p.onStop}
              className="flex items-center gap-1.5 rounded-lg border border-border-soft px-3 py-2 text-sm text-subink transition hover:bg-surface-2"
              data-testid="gen-stop"
            >
              <Stop size={14} weight="fill" /> 停止
            </button>
          ) : (
            <button
              onClick={p.onSend}
              disabled={!p.value.trim()}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-soft-sm transition hover:opacity-90 disabled:opacity-40"
              data-testid="gen-send"
            >
              <PaperPlaneRight size={14} weight="fill" /> 发送
            </button>
          )}
        </div>
        {p.attachment && p.presets.length === 3 && (
          <div className="flex flex-wrap gap-1.5 px-1 pb-1">
            {p.presets.map((s) => (
              <button
                key={s}
                onClick={() => p.onValueChange(s)}
                className="rounded-full border border-border-soft bg-surface-2 px-3 py-1 text-xs text-subink transition hover:border-accent hover:text-accent"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {p.error && <div className="px-1 text-xs text-err">{p.error}</div>}
      </div>
    </div>
  );
}

function InputControl(p: Props & { input: AgentUiInput }) {
  if (p.input.mode === "image") return <ImageInput p={p} />;
  if (p.input.mode === "tabular") return <TabularInput p={p} />;
  if (p.input.mode === "vector") return <VectorInput p={p} />;
  return <TextInput p={p} />;
}

function Chip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-weak px-2.5 py-0.5 text-[11px] font-medium text-ok">
      {label}
      <button onClick={onClear} title="移除"><X size={11} /></button>
    </span>
  );
}

function ImageInput({ p }: { p: Props & { input: AgentUiInput } }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [name, setName] = useState("");

  async function pick(f: File) {
    setName(f.name);
    setPreview(URL.createObjectURL(f));
    await p.onUpload(f);
  }

  return (
    <div
      className="flex items-center gap-2 px-1"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f) pick(f);
      }}
    >
      <button
        onClick={() => fileRef.current?.click()}
        className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-border-soft bg-surface-2 text-subink transition hover:border-accent"
        data-testid="gen-upload"
      >
        {preview ? <img src={preview} alt="preview" className="h-full w-full object-contain" /> : <UploadSimple size={18} />}
      </button>
      <div className="min-w-0 flex-1 text-xs text-subink">
        {name ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-ink">{name}</span>
            {p.uploading ? (
              <span className="inline-flex items-center gap-1 text-subink"><CircleNotch size={12} className="animate-spin" />解析中</span>
            ) : p.attachment ? (
              <Chip label={`${p.attachment.vector_len ?? ""} 维就绪`} onClear={() => { setPreview(null); setName(""); p.onAttachmentChange(null); }} />
            ) : null}
          </div>
        ) : (
          <span>拖拽或点击放入图片（模型需要 {p.ui.input.mode === "image" ? "图像" : "输入"}）</span>
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept={p.input.accept || "image/*"}
        className="hidden"
        onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])}
      />
    </div>
  );
}

function TabularInput({ p }: { p: Props & { input: AgentUiInput } }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const names = p.ui.input.feature_names ?? [];
  const [vals, setVals] = useState<string[]>(() => (p.ui.input.sample ?? []).map(String));

  function applyForm() {
    const feats = vals.map((v) => Number(v));
    if (feats.some((v) => !Number.isFinite(v))) return;
    const row: Record<string, string> = {};
    names.forEach((n, i) => { row[n] = String(feats[i]); });
    p.onAttachmentChange({ input_type: "tabular", rows: [{ features: feats, row }] });
    setFormOpen(false);
  }

  return (
    <div className="px-1">
      <div className="flex items-center gap-2">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex h-10 items-center gap-2 rounded-xl border-2 border-dashed border-border-soft bg-surface-2 px-3 text-xs text-subink transition hover:border-accent"
          data-testid="gen-upload"
        >
          <Table size={15} />
          {name || "选择 CSV"}
        </button>
        <button
          onClick={() => setFormOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-accent hover:underline"
        >
          <Sliders size={13} /> 单样本表单
        </button>
        {p.uploading && <CircleNotch size={13} className="animate-spin text-subink" />}
        {p.attachment?.rows && (
          <Chip
            label={`${p.attachment.rows.length} 行 × ${p.attachment.rows[0]?.features.length ?? 0} 列`}
            onClear={() => { setName(""); p.onAttachmentChange(null); }}
          />
        )}
      </div>
      {formOpen && (
        <div className="mt-2 max-h-52 overflow-auto rounded-lg border border-border-soft p-2">
          <div className="grid grid-cols-2 gap-1.5">
            {names.map((n, i) => (
              <label key={n} className="flex items-center gap-1.5 text-[11px] text-subink">
                <span className="w-28 shrink-0 truncate" title={n}>{n}</span>
                <input
                  value={vals[i] ?? ""}
                  onChange={(e) => {
                    const next = [...vals];
                    next[i] = e.target.value;
                    setVals(next);
                  }}
                  className="min-w-0 flex-1 rounded border border-border-soft bg-white px-1.5 py-1 text-ink outline-none focus:border-accent"
                />
              </label>
            ))}
          </div>
          <button onClick={applyForm} className="mt-2 rounded-lg bg-primary px-3 py-1 text-xs text-white">应用输入</button>
        </div>
      )}
      <input
        ref={fileRef}
        type="file"
        accept={p.input.accept || ".csv,text/csv"}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) { setName(f.name); p.onUpload(f); }
        }}
      />
    </div>
  );
}

function VectorInput({ p }: { p: Props & { input: AgentUiInput } }) {
  const [text, setText] = useState((p.ui.input.sample ?? []).join(", "));
  return (
    <div className="flex items-center gap-2 px-1">
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const feats = e.target.value.replace(/,/g, " ").split(/\s+/).filter(Boolean).map(Number);
          if (feats.every((v) => Number.isFinite(v)) && feats.length === (p.ui.input.dim ?? feats.length)) {
            p.onAttachmentChange({ input_type: "vector", features: feats });
          }
        }}
        rows={1}
        className="scroll-thin flex-1 resize-none rounded-lg border border-border-soft bg-surface-2 px-2 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
      />
      {p.attachment && <Chip label={`${p.attachment.features?.length ?? 0} 维`} onClear={() => p.onAttachmentChange(null)} />}
    </div>
  );
}

function TextInput({ p }: { p: Props & { input: AgentUiInput } }) {
  const [text, setText] = useState("");
  return (
    <div className="flex items-center gap-2 px-1">
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          p.onAttachmentChange(e.target.value ? { input_type: "text", text: e.target.value } : null);
        }}
        rows={1}
        placeholder="文本输入…"
        className="scroll-thin flex-1 resize-none rounded-lg border border-border-soft bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none focus:border-accent"
        data-testid="gen-text"
      />
    </div>
  );
}
