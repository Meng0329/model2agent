// Left column: task history + new-task entry.
import { Plus, MessageSquare, Trash2, Cpu, CheckCircle2, AlertCircle, Boxes } from "lucide-react";
import { useTasks } from "../state/TasksProvider";
import { cn } from "./ui";

export function TaskList({ onNewTask }: { onNewTask: () => void }) {
  const { tasks, currentTask, setCurrent, deleteTask } = useTasks();

  return (
    <div className="flex h-full flex-col bg-surface border-r border-border">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 font-semibold text-ink">
          <Boxes size={18} className="text-accent" />
          <span>Model2Agent</span>
        </div>
      </div>

      <div className="p-3">
        <button
          onClick={onNewTask}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700"
        >
          <Plus size={16} /> 新建任务
        </button>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto px-2 pb-3">
        <div className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-subink">最近任务</div>
        {tasks.length === 0 && (
          <div className="px-3 py-8 text-center text-sm text-subink">
            还没有任务，点击「新建任务」开始。
          </div>
        )}
        {tasks.map((t) => {
          const active = currentTask?.id === t.id;
          return (
            <div
              key={t.id}
              className={cn(
                "group mb-1.5 cursor-pointer rounded-lg border px-3 py-2.5 transition",
                active ? "border-accent bg-teal-50" : "border-transparent hover:border-border hover:bg-white"
              )}
              onClick={() => setCurrent(t)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <MessageSquare size={15} className="shrink-0 text-subink" />
                  <span className="truncate text-sm font-medium text-ink">{t.name}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}
                  className="shrink-0 rounded p-1 text-subink opacity-0 transition hover:bg-red-50 hover:text-err group-hover:opacity-100"
                  title="删除任务"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-xs text-subink">
                {t.status === "error" ? (
                  <AlertCircle size={12} className="text-err" />
                ) : t.has_generated ? (
                  <CheckCircle2 size={12} className="text-ok" />
                ) : (
                  <Cpu size={12} />
                )}
                <span className="truncate">{t.asset_slug || "未识别资产"}</span>
                <span className="ml-auto shrink-0">{new Date(t.updated_at).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
