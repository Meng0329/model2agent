import { useEffect, useState } from "react";
import { useTasks } from "./state/TasksProvider";
import { TaskList } from "./components/TaskList";
import { NewTaskPage } from "./components/NewTaskPage";
import { DeviceSetupModal } from "./components/DeviceSetupModal";
import { Workbench } from "./components/Workbench";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { SlidersHorizontal, PanelLeftClose, PanelLeftOpen, PanelRightOpen, PanelRightClose } from "lucide-react";
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
    <div className="flex h-full w-full overflow-hidden">
      {/* Left */}
      <div className={cn("shrink-0 transition-all", leftOpen ? "w-72" : "w-12")}>
        {leftOpen ? (
          <TaskList onNewTask={openNewTask} />
        ) : (
          <div className="flex h-full flex-col items-center gap-3 border-r border-border bg-surface py-3">
            <button onClick={() => setLeftOpen(true)} className="rounded p-2 text-subink hover:bg-white" title="展开任务栏"><PanelLeftOpen size={18} /></button>
            <button onClick={openNewTask} className="rounded p-2 text-accent hover:bg-white" title="新建任务"><PanelLeftClose size={18} className="hidden" /> <span className="text-accent">+</span></button>
          </div>
        )}
      </div>

      {/* Center */}
      <div className="flex min-w-0 flex-1 flex-col">
        {!leftOpen && (
          <button onClick={() => setLeftOpen(true)} className="border-b border-border bg-surface px-3 py-2 text-left text-sm text-subink hover:bg-white">展开任务栏</button>
        )}
        <div className="flex items-center justify-between border-b border-border bg-white px-4 py-2.5">
          <div className="min-w-0 truncate text-sm font-medium text-ink">
            {currentTask ? currentTask.name : "未选择任务"}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setDeviceOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-subink hover:bg-surface"
              title="设备设置"
            >
              <SlidersHorizontal size={14} /> {device || "设备"}
            </button>
            <button onClick={() => setRightOpen((v) => !v)} className="rounded-lg border border-border p-1.5 text-subink hover:bg-surface" title="工作区">
              {rightOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
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
        <div className="w-[34%] min-w-[320px] max-w-[560px] shrink-0 border-l border-border">
          {currentTask ? <WorkspacePanel task={currentTask} /> : <div className="flex h-full items-center justify-center text-sm text-subink">选择任务查看工作区</div>}
        </div>
      )}

      <DeviceSetupModal open={deviceOpen || deviceGate} onClose={() => { setDeviceOpen(false); setDeviceGate(false); }} />
    </div>
  );
}

function EmptyState({ onNewTask }: { onNewTask: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-surface text-center">
      <div className="rounded-2xl border border-border bg-white px-8 py-10">
        <div className="text-base font-medium text-ink">开始你的第一个模型到 Agent 的转化</div>
        <p className="mt-1 text-sm text-subink">上传训练好的模型资产，Builder 会自主分析并生成可独立运行的 Agent。</p>
        <button onClick={onNewTask} className="mt-5 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-teal-700">新建任务</button>
      </div>
    </div>
  );
}
