// Right panel: current task's generated artifacts (Files / Preview / Export tabs).
// P1: tabs shell only. P3 wires the file tree + viewer; P6 wires preview/export.
import { useState } from "react";
import { Files, PlayCircle, Download, FolderOpen } from "lucide-react";
import type { Task } from "../types";
import { cn, Badge } from "./ui";

export function WorkspacePanel({ task }: { task: Task }) {
  const [tab, setTab] = useState<"files" | "preview" | "export">("files");

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center gap-1 border-b border-border px-2 py-2">
        <TabBtn active={tab === "files"} onClick={() => setTab("files")} icon={<Files size={14} />} label="文件" />
        <TabBtn active={tab === "preview"} onClick={() => setTab("preview")} icon={<PlayCircle size={14} />} label="预览" />
        <TabBtn active={tab === "export"} onClick={() => setTab("export")} icon={<Download size={14} />} label="导出" />
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "files" && (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-subink">
            <FolderOpen size={26} className="text-subink/50" />
            <div className="text-sm">工作区还没有生成文件</div>
            <div className="text-xs text-subink/70">Builder 生成后，文件会出现在这里</div>
          </div>
        )}
        {tab === "preview" && (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-subink">
            <PlayCircle size={26} className="text-subink/50" />
            <div className="text-sm">尚未启动预览</div>
          </div>
        )}
        {tab === "export" && (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-subink">
            <Download size={26} className="text-subink/50" />
            <div className="text-sm">Docker 状态：<Badge tone="neutral">{task.docker_status}</Badge></div>
          </div>
        )}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition", active ? "bg-surface font-medium text-ink" : "text-subink hover:bg-surface")}
    >
      {icon} {label}
    </button>
  );
}
