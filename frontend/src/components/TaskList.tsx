// Left column: task history + new-task entry.
import { Plus, ChatCircle, Trash, Cpu, CheckCircle, WarningCircle, Hexagon, SidebarSimple } from "@phosphor-icons/react";
import { useTasks } from "../state/TasksProvider";
import { cn } from "./ui";

export function TaskList({ onNewTask, onCollapse }: { onNewTask: () => void; onCollapse: () => void }) {
  const { tasks, currentTask, setCurrent, deleteTask } = useTasks();

  return (
    <div className="flex h-full flex-col border-r border-border-soft bg-surface-2">
      <div className="flex items-center justify-between border-b border-border-soft px-4 py-3">
        <div className="flex items-center gap-2 font-semibold text-ink">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ok text-white shadow-soft-sm">
            <Hexagon size={16} weight="fill" />
          </span>
          <span>Model2Agent</span>
        </div>
        <button
          onClick={onCollapse}
          className="rounded-lg p-1.5 text-subink transition hover:bg-white"
          title="折叠任务栏"
        >
          <SidebarSimple size={17} />
        </button>
      </div>

      <div className="p-3">
        <button
          onClick={onNewTask}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-sm font-medium text-white shadow-soft-sm transition hover:opacity-90"
        >
          <Plus size={16} weight="bold" /> 新建任务
        </button>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto px-2 pb-3">
        <div className="px-2 pb-1 text-[11px] font-bold uppercase tracking-wider text-subink">最近任务</div>
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
                "group mb-1.5 cursor-pointer rounded-xl border px-3 py-2.5 transition",
                active
                  ? "border-accent bg-accent-soft"
                  : "border-transparent hover:border-border-soft hover:bg-white"
              )}
              onClick={() => setCurrent(t)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <ChatCircle size={15} className={cn("shrink-0", active ? "text-accent" : "text-subink")} />
                  <span className="truncate text-sm font-medium text-ink">{t.name}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}
                  className="shrink-0 rounded p-1 text-subink opacity-0 transition hover:bg-err-weak hover:text-err group-hover:opacity-100"
                  title="删除任务"
                >
                  <Trash size={14} />
                </button>
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-xs text-subink">
                {t.status === "error" ? (
                  <WarningCircle size={12} className="text-err" />
                ) : t.has_generated ? (
                  <CheckCircle size={12} className="text-ok" />
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
