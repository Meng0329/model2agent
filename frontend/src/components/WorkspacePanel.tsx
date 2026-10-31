// Right panel: current task's generated artifacts (Files / Preview / Export tabs).
// P3: real file tree + viewer, live-synced via workspace_changed SSE.
import { useEffect, useMemo, useRef, useState } from "react";
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

  // initial load + reset selection when switching tasks (avoid stale paths → 404)
  useEffect(() => {
    setSel(null);
    setContent(null);
    loadFiles();
    // eslint-disable-next-line
  }, [taskId]);
  useEffect(() => {
    if (tab !== "files") return;
    const t = setInterval(() => loadFiles(), 2500);
    return () => clearInterval(t);
  }, [tab, taskId]);

  const openFile = async (path: string) => {
    if (!path) return;
    setSel(path); setLoading("content");
    try {
      const r = await fetch(`/api/tasks/${taskId}/files/content?path=${encodeURIComponent(path)}`).then((r) => r.json());
      setContent(r);
    } catch { setContent(null); }
    setLoading(false);
  };

  const [previewBusy, setPreviewBusy] = useState(false);

  const preview = () => {
    fetch(`/api/tasks/${taskId}/preview/status`).then((r) => r.json()).then((s) => {
      setPreviewState(s);
      if (s.state === "running" && s.url) setTab("preview");
    }).catch(() => {});
  };

  const startPreview = async () => {
    setPreviewBusy(true);
    try {
      const r = await fetch(`/api/tasks/${taskId}/preview/start`, { method: "POST" });
      const s = await r.json();
      setPreviewState(s);
      setTab("preview");
    } catch (e) {
      setPreviewState({ state: "error", error: String(e) });
    } finally {
      setPreviewBusy(false);
    }
  };

  const stopPreview = async () => {
    setPreviewBusy(true);
    try {
      await fetch(`/api/tasks/${taskId}/preview/stop`, { method: "POST" });
      setPreviewState({ state: "stopped" });
    } finally {
      setPreviewBusy(false);
    }
  };

  // poll preview status while the preview tab is open
  useEffect(() => {
    if (tab !== "preview") return;
    preview();
    const t = setInterval(preview, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [tab, taskId]);

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
          <PreviewTab task={task} state={previewState} zoom={zoom} setZoom={setZoom}
                      onStart={startPreview} onStop={stopPreview} busy={previewBusy}
                      onRefresh={() => preview()} />
        )}
        {tab === "export" && (
          <ExportTab task={task} />
        )}
      </div>
    </div>
  );
}

function FileTree({ files, sel, onOpen }: { files: FileItem[]; sel: string | null; onOpen: (p: string) => void }) {
  // build a recursive view: directories expand, files open content. A directory is
  // never passed to onOpen (that would 404 the content endpoint on a dir path).
  const build = (prefix: string): React.ReactNode[] => {
    const children = files.filter((f) => {
      if (prefix && !f.path.startsWith(prefix + "/")) return false;
      const rest = prefix ? f.path.slice(prefix.length + 1) : f.path;
      return rest.length > 0 && !rest.includes("/");
    });
    return children.map((c) => <TreeNode key={c.path} f={c} files={files} sel={sel} onOpen={onOpen} depth={0} />);
  };
  return (
    <div className="w-60 shrink-0 overflow-auto bg-surface/60 p-2">
      {build("")}
      {files.length === 0 && <div className="px-2 py-6 text-center text-xs text-subink">工作区还没有文件</div>}
    </div>
  );
}

function TreeNode({ f, files, sel, onOpen, depth }: { f: FileItem; files: FileItem[]; sel: string | null; onOpen: (p: string) => void; depth: number }) {
  const [isOpen, setIsOpen] = useState(depth < 1);
  if (f.is_dir) {
    const kids = files.filter((x) => x.path.startsWith(f.path + "/") && x.path.slice(f.path.length + 1).split("/").length === 1);
    return (
      <div>
        <button onClick={() => setIsOpen((o) => !o)} className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-sm text-ink hover:bg-white" style={{ paddingLeft: 8 + depth * 14 }}>
          <ChevronRight size={13} className={cn("shrink-0 text-subink transition", isOpen && "rotate-90")} />
          <Folder size={14} className="shrink-0 text-amber-500" /> <span className="truncate">{f.name}</span>
        </button>
        {isOpen && kids.map((c) => <TreeNode key={c.path} f={c} files={files} sel={sel} onOpen={onOpen} depth={depth + 1} />)}
      </div>
    );
  }
  const active = sel === f.path;
  return (
    <button onClick={() => onOpen(f.path)} className={cn("flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm", active ? "bg-accent/10 text-accent" : "text-ink hover:bg-white")} style={{ paddingLeft: 22 + depth * 14 }}>
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

function PreviewTab({ task, state, zoom, setZoom, onStart, onStop, busy, onRefresh }: {
  task: Task;
  state: { state: string; url?: string; proxy_url?: string; error?: string };
  zoom: boolean;
  setZoom: (z: boolean) => void;
  onStart: () => void;
  onStop: () => void;
  busy: boolean;
  onRefresh: () => void;
}) {
  const running = state.state === "running";
  // Default to the same-origin proxy: works through SSH tunnels / remote access
  // without forwarding the random preview port. 直连 is offered for LAN users.
  const [useProxy, setUseProxy] = useState(true);
  const src = useProxy && state.proxy_url ? state.proxy_url : state.url;
  return (
    <div className="relative flex h-full flex-col">
      {/* toolbar stays above the zoomed iframe (z-50) so 放大/还原 remain clickable */}
      <div className="relative z-50 flex items-center gap-2 border-b border-border bg-white px-3 py-2 text-sm">
        <PlayCircle size={15} className="text-subink" />
        <span className="text-subink">预览状态</span>
        <Badge tone={running ? "ok" : state.state === "error" ? "err" : "neutral"}>{state.state}</Badge>
        {running ? (
          <button onClick={onStop} disabled={busy} className="rounded-lg border border-border px-2 py-1 text-xs text-err hover:bg-surface disabled:opacity-50">停止</button>
        ) : (
          <button onClick={onStart} disabled={busy} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50" data-testid="preview-start">
            {busy ? "启动中…" : "启动预览"}
          </button>
        )}
        {running && state.proxy_url && state.url && (
          <button onClick={() => setUseProxy(!useProxy)} className="rounded-lg border border-border px-2 py-1 text-xs text-subink hover:bg-surface" title="切换同源代理 / 局域网直连">
            {useProxy ? "同源代理" : "直连"}
          </button>
        )}
        <button onClick={onRefresh} className="rounded-lg px-2 py-1 text-xs text-subink hover:bg-surface">刷新</button>
        <button onClick={() => setZoom(!zoom)} className="rounded-lg px-2 py-1 text-xs text-subink hover:bg-surface">{zoom ? "还原" : "放大"}</button>
      </div>
      <div className="scroll-thin flex-1 overflow-auto bg-surface">
        {src ? (
          <iframe src={src} className={cn("border-0 bg-white", zoom ? "absolute inset-0 z-40 h-full w-full" : "h-full w-full")} title="generated-agent-preview" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-subink">
            <PlayCircle size={26} className="text-subink/40" />
            <div className="text-sm">尚未启动预览</div>
            <div className="text-xs text-subink/70">生成项目后点击「启动预览」，将真实启动独立进程</div>
            {state.error && <div className="max-w-full px-4 text-center text-xs text-err">{state.error}</div>}
          </div>
        )}
      </div>
      {zoom && (
        <button
          onClick={() => setZoom(false)}
          aria-label="还原"
          title="还原"
          className="fixed right-4 top-4 z-50 rounded-full bg-white p-1.5 shadow"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}

function ExportTab({ task }: { task: Task }) {
  const [status, setStatus] = useState<{ has_project: boolean; has_dockerfile: boolean; docker_status: string; docker_gate_enabled: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const taskId = task.id;

  const load = () => {
    fetch(`/api/tasks/${taskId}/export/status`).then((r) => r.json()).then(setStatus).catch(() => {});
  };
  useEffect(load, [taskId]);

  const verifyDocker = async () => {
    setBusy(true); setNote("");
    try {
      const r = await fetch(`/api/tasks/${taskId}/export/verify-docker`, { method: "POST" });
      const j = await r.json();
      setNote(j.note || `结果：${j.status}`);
      load();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  const hasProject = status?.has_project;
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-2 text-sm">
        <Download size={15} className="text-subink" /> 导出 Generated Agent
      </div>

      {!hasProject ? (
        <div className="rounded-lg border border-border bg-surface px-3 py-6 text-center text-sm text-subink">
          <FolderOpen size={22} className="mx-auto mb-2 text-subink/40" />
          尚未生成可下载项目
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <a
              href={`/api/tasks/${taskId}/export`}
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90"
              data-testid="export-zip"
            >
              <Download size={15} /> 下载 ZIP（含 Dockerfile，不含密钥）
            </a>
            <p className="mt-1 text-xs text-subink">包含 project/、真实权重、Dockerfile、requirements 与已构建的 React UI。</p>
          </div>

          <div className="rounded-lg border border-border p-3">
            <div className="mb-2 flex items-center gap-2 text-sm">
              Docker 状态
              <Badge tone={status?.docker_status === "verified" ? "ok" : status?.docker_status === "failed" ? "err" : "neutral"}>{status?.docker_status}</Badge>
            </div>
            <p className="mb-2 text-xs text-subink">
              {status?.docker_gate_enabled
                ? "已启用 V2_DOCKER=1：将真实构建镜像、启动容器并跑一次真实推理。"
                : "未启用 V2_DOCKER=1：不会执行真实构建，状态如实记为 unverified（绝不虚报成功）。"}
            </p>
            <button
              onClick={verifyDocker}
              disabled={busy || !status?.has_dockerfile}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface disabled:opacity-50"
              data-testid="verify-docker"
            >
              {busy ? "验证中…" : "验证 Docker"}
            </button>
            {note && <div className="mt-2 text-xs text-subink">{note}</div>}
          </div>
        </div>
      )}
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
