// Right panel: current task's generated artifacts (Files / Preview / Export tabs).
// P3: real file tree + viewer, live-synced via workspace_changed SSE.
import { useEffect, useMemo, useState } from "react";
import { Files, PlayCircle, Download, FolderOpen, Folder, FileCode, FileText, ChevronRight, RefreshCw, Eye, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Task } from "../types";
import { cn, Badge } from "./ui";

interface FileItem { path: string; name: string; is_dir: boolean; size: number; ext?: string; is_text?: boolean; }

export function WorkspacePanel({ task }: { task: Task }) {
  const [tab, setTab] = useState<"files" | "preview" | "export">("files");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [content, setContent] = useState<{ content: string; is_binary: boolean; size: number } | null>(null);
  const [loading, setLoading] = useState<false | "content">(false);
  const [previewState, setPreviewState] = useState<{ state: string; url?: string; error?: string }>({ state: "stopped" });
  const [zoom, setZoom] = useState(false);
  const taskId = task.id;

  const loadFiles = async () => {
    try {
      const r = await fetch(`/api/tasks/${taskId}/files`).then((r) => r.json());
      setFiles(r.files as FileItem[]);
      // auto-select a previewable file if none selected
      if (!sel) {
        const p = (r.files as FileItem[]).find((f) => !f.is_dir && (f.ext === ".md" || f.ext === ".json" || f.ext === ".py" || f.is_text));
        if (p) setSel(p.path);
      }
    } catch { /* ignore */ }
  };

  // initial load + live refresh when the tab is open and files change
  useEffect(() => { loadFiles(); /* eslint-disable-next-line */ }, [taskId]);
  useEffect(() => {
    if (tab !== "files") return;
    const t = setInterval(() => loadFiles(), 2500);
    return () => clearInterval(t);
  }, [tab, taskId]);

  const openFile = async (path: string) => {
    setSel(path); setLoading("content");
    try {
      const r = await fetch(`/api/tasks/${taskId}/files/content?path=${encodeURIComponent(path)}`).then((r) => r.json());
      setContent(r);
    } catch { setContent(null); }
    setLoading(false);
  };

  const preview = () => {
    fetch(`/api/tasks/${taskId}/preview/status`).then((r) => r.json()).then((s) => {
      setPreviewState(s);
      if (s.state === "running" && s.url) setTab("preview");
    }).catch(() => {});
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center gap-1 border-b border-border px-2 py-2">
        <TabBtn active={tab === "files"} onClick={() => setTab("files")} icon={<Files size={14} />} label="文件" />
        <TabBtn active={tab === "preview"} onClick={() => setTab("preview")} icon={<PlayCircle size={14} />} label="预览" />
        <TabBtn active={tab === "export"} onClick={() => setTab("export")} icon={<Download size={14} />} label="导出" />
        <button onClick={loadFiles} className="ml-auto rounded-lg p-1.5 text-subink hover:bg-surface" title="刷新"><RefreshCw size={14} /></button>
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {tab === "files" && (
          <div className="flex h-full">
            <FileTree files={files} sel={sel} onOpen={openFile} />
            <div className="min-w-0 flex-1 border-l border-border">
              {sel && content ? <FileViewer path={sel} data={content} loading={loading === "content"} /> : (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-subink">
                  <FileText size={24} className="text-subink/40" />
                  <div className="text-sm">选择左侧文件查看内容</div>
                </div>
              )}
            </div>
          </div>
        )}
        {tab === "preview" && (
          <PreviewTab task={task} state={previewState} zoom={zoom} setZoom={setZoom} onRefresh={() => preview()} />
        )}
        {tab === "export" && (
          <ExportTab task={task} />
        )}
      </div>
    </div>
  );
}

function FileTree({ files, sel, onOpen }: { files: FileItem[]; sel: string | null; onOpen: (p: string) => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const dirs = useMemo(() => files.filter((f) => f.is_dir), [files]);
  const leaves = useMemo(() => files.filter((f) => !f.is_dir), [files]);
  const topDirs = dirs.filter((d) => !d.path.includes("/"));
  const topFiles = leaves.filter((f) => !f.path.includes("/"));

  return (
    <div className="w-60 shrink-0 bg-surface/60 p-2">
      {topDirs.map((d) => {
        const isOpen = open[d.path] !== false;
        const children = files.filter((f) => f.path.startsWith(d.path + "/") && f.path.slice(d.path.length + 1).split("/").length === 1);
        return (
          <div key={d.path}>
            <button onClick={() => setOpen((o) => ({ ...o, [d.path]: !isOpen }))} className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-sm text-ink hover:bg-white">
              <ChevronRight size={13} className={cn("shrink-0 text-subink transition", isOpen && "rotate-90")} />
              <Folder size={14} className="shrink-0 text-amber-500" /> <span className="truncate">{d.name}</span>
            </button>
            {isOpen && children.map((c) => <Leaf key={c.path} f={c} sel={sel} onOpen={onOpen} indent />)}
          </div>
        );
      })}
      {topFiles.map((f) => <Leaf key={f.path} f={f} sel={sel} onOpen={onOpen} />)}
      {files.length === 0 && <div className="px-2 py-6 text-center text-xs text-subink">工作区还没有文件</div>}
    </div>
  );
}

function Leaf({ f, sel, onOpen, indent }: { f: FileItem; sel: string | null; onOpen: (p: string) => void; indent?: boolean }) {
  const active = sel === f.path;
  return (
    <button onClick={() => onOpen(f.path)} className={cn("flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm", indent && "pl-6", active ? "bg-accent/10 text-accent" : "text-ink hover:bg-white")}>
      <FileCode size={13} className={cn("shrink-0", active ? "text-accent" : "text-subink")} />
      <span className="truncate">{f.name}</span>
    </button>
  );
}

function FileViewer({ path, data, loading }: { path: string; data: { content: string; is_binary: boolean; size: number }; loading: boolean }) {
  const ext = path.split(".").pop() || "";
  const isMd = ext === "md";
  const isJson = ext === "json";
  if (loading) return <div className="p-4 text-sm text-subink">加载中…</div>;
  if (data.is_binary) return <div className="p-4 text-sm text-subink">二进制文件（{data.size} 字节），暂不支持内联预览</div>;
  if (isMd) return <div className="prose max-w-none p-4 text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]}>{data.content}</ReactMarkdown></div>;
  if (isJson) {
    try { return <pre className="scroll-thin h-full overflow-auto p-4 text-xs">{JSON.stringify(JSON.parse(data.content), null, 2)}</pre>; }
    catch { /* fall through */ }
  }
  return <pre className="scroll-thin h-full overflow-auto p-4 text-xs leading-relaxed">{data.content}</pre>;
}

function PreviewTab({ task, state, zoom, setZoom, onRefresh }: { task: Task; state: { state: string; url?: string; error?: string }; zoom: boolean; setZoom: (z: boolean) => void; onRefresh: () => void }) {
  return (
    <div className="relative flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-sm">
        <PlayCircle size={15} className="text-subink" />
        <span className="text-subink">预览状态</span>
        <Badge tone={state.state === "running" ? "ok" : state.state === "error" ? "err" : "neutral"}>{state.state}</Badge>
        <button onClick={onRefresh} className="ml-auto rounded-lg px-2 py-1 text-xs text-subink hover:bg-surface">刷新</button>
        <button onClick={() => setZoom(!zoom)} className="rounded-lg px-2 py-1 text-xs text-subink hover:bg-surface">{zoom ? "还原" : "放大"}</button>
      </div>
      <div className="scroll-thin flex-1 overflow-auto bg-surface">
        {state.url ? (
          <iframe src={state.url} className="h-full w-full border-0" title="generated-agent-preview" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-subink">
            <PlayCircle size={26} className="text-subink/40" />
            <div className="text-sm">尚未启动预览</div>
            <div className="text-xs text-subink/70">在对话中让 Builder 生成后，从「导出」或对话里启动</div>
            {state.error && <div className="px-4 text-xs text-err">{state.error}</div>}
          </div>
        )}
      </div>
      {zoom && <button onClick={() => setZoom(false)} className="absolute right-3 top-3 rounded-full bg-white p-1.5 shadow"><X size={16} /></button>}
    </div>
  );
}

function ExportTab({ task }: { task: Task }) {
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-2 text-sm">
        <Download size={15} className="text-subink" /> Docker 状态
        <Badge tone={task.docker_status === "verified" ? "ok" : task.docker_status === "failed" ? "err" : "neutral"}>{task.docker_status}</Badge>
      </div>
      <p className="text-xs text-subink">生成 Agent 项目后，可下载含 Dockerfile 的完整 ZIP（不含密钥）。</p>
      <div className="mt-3 rounded-lg border border-border bg-surface px-3 py-6 text-center text-sm text-subink">
        <FolderOpen size={22} className="mx-auto mb-2 text-subink/40" />
        尚未生成可下载项目
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition", active ? "bg-surface font-medium text-ink" : "text-subink hover:bg-surface")}>
      {icon} {label}
    </button>
  );
}
