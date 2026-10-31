import { useEffect, useState } from "react";
import { useTasks } from "./state/TasksProvider";
import { TaskList } from "./components/TaskList";
import { NewTaskPage } from "./components/NewTaskPage";
import { DeviceSetupModal } from "./components/DeviceSetupModal";
import { Workbench } from "./components/Workbench";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { Sliders, SidebarSimple, Sidebar, Plus } from "@phosphor-icons/react";
import { cn } from "./components/ui";

export default function App() {
  const { loading, currentTask, deviceConfigured, device, setCurrent } = useTasks();
  const [newTask, setNewTask] = useState(false);
  const [deviceOpen, setDeviceOpen] = useState(false);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  // first-run device gate: only open once devices finished loading AND none configured
  const [deviceGate, setDeviceGate] = useState(false);
  useEffect(() => {
    if (!loading && !deviceConfigured) setDeviceGate(true);
  }, [loading, deviceConfigured]);

  const openNewTask = () => {
    if (!deviceConfigured) { setDeviceOpen(true); return; }
    setNewTask(true);
  };

  if (loading) {
    return <div className="flex h-full items-center justify-center text-subink">加载中…</div>;
  }

  return (
    <div className="flex h-full w-full overflow-hidden bg-bg">
      {/* Left */}
      <div className={cn("shrink-0 transition-all", leftOpen ? "w-72" : "w-12")}>
        {leftOpen ? (
          <TaskList onNewTask={openNewTask} />
        ) : (
          <div className="flex h-full flex-col items-center gap-3 border-r border-border-soft bg-surface-2 py-3">
            <button onClick={() => setLeftOpen(true)} className="rounded-lg p-2 text-subink hover:bg-white" title="展开任务栏"><Sidebar size={18} /></button>
            <button onClick={openNewTask} className="rounded-lg p-2 text-accent hover:bg-white" title="新建任务"><Plus size={18} weight="bold" /></button>
          </div>
        )}
      </div>

      {/* Center */}
      <div className="flex min-w-0 flex-1 flex-col">
        {!leftOpen && (
          <button onClick={() => setLeftOpen(true)} className="border-b border-border-soft bg-surface-2 px-3 py-2 text-left text-sm text-subink hover:bg-white">展开任务栏</button>
        )}
        <div className="flex items-center justify-between border-b border-border-soft bg-white px-4 py-2.5">
          <div className="min-w-0 truncate text-sm font-semibold text-ink">
            {currentTask ? currentTask.name : "未选择任务"}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setDeviceOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-border-soft px-2.5 py-1.5 text-xs text-subink transition hover:bg-surface-2"
              title="设备设置"
            >
              <Sliders size={14} /> {device || "设备"}
            </button>
            <button onClick={() => setRightOpen((v) => !v)} className="rounded-lg border border-border-soft p-1.5 text-subink transition hover:bg-surface-2" title="工作区">
              {rightOpen ? <SidebarSimple size={16} /> : <Sidebar size={16} />}
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {newTask ? (
            <NewTaskPage onCreated={() => { setNewTask(false); setDeviceGate(false); }} onCancel={() => setNewTask(false)} />
          ) : currentTask ? (
            <Workbench task={currentTask} />
          ) : (
            <EmptyState onNewTask={openNewTask} />
          )}
        </div>
      </div>

      {/* Right */}
      {rightOpen && (
        <div className="w-[34%] min-w-[320px] max-w-[560px] shrink-0 border-l border-border-soft">
          {currentTask ? <WorkspacePanel task={currentTask} /> : <div className="flex h-full items-center justify-center text-sm text-subink">选择任务查看工作区</div>}
        </div>
      )}

      <DeviceSetupModal open={deviceOpen || deviceGate} onClose={() => { setDeviceOpen(false); setDeviceGate(false); }} />
    </div>
  );
}

function EmptyState({ onNewTask }: { onNewTask: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-bg text-center">
      <div className="w-full max-w-md rounded-2xl border border-border-soft bg-white px-8 py-10 shadow-soft">
        <div className="mx-auto mb-4 flex h-16 w-20 items-center justify-center rounded-2xl bg-surface-2 text-subink/50">
          <SidebarSimple size={34} weight="duotone" />
        </div>
        <div className="text-base font-semibold text-ink">开始你的第一个模型到 Agent 的转化</div>
        <p className="mx-auto mt-1 max-w-xs text-sm leading-relaxed text-subink">上传训练好的模型资产，Builder 会自主分析并生成可独立运行的 Agent。</p>
        <button onClick={onNewTask} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-white shadow-soft-sm transition hover:opacity-90">
          <Plus size={16} weight="bold" /> 新建任务
        </button>
      </div>
    </div>
  );
}
