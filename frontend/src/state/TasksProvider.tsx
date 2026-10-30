// Global product state: tasks list, current task, device setting.
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import type { DeviceInfo, Task } from "../types";

interface TasksCtx {
  tasks: Task[];
  currentTask: Task | null;
  devices: DeviceInfo[];
  device: string;
  deviceConfigured: boolean;
  loading: boolean;
  refreshTasks: () => Promise<void>;
  refreshCurrent: () => Promise<void>;
  createTask: (form: FormData) => Promise<Task>;
  deleteTask: (id: string) => Promise<void>;
  setCurrent: (t: Task | null) => void;
  patchCurrent: (p: { name?: string; goal?: string }) => Promise<void>;
  selectDevice: (d: string) => Promise<void>;
  refreshDevices: () => Promise<void>;
}

const Ctx = createContext<TasksCtx | null>(null);

export function TasksProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [currentTask, setCurrentTask] = useState<Task | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [device, setDevice] = useState<string>("");
  const [deviceConfigured, setDeviceConfigured] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshTasks = async () => {
    const t = await api.listTasks();
    setTasks(t);
  };
  const refreshCurrent = async () => {
    if (!currentTask) return;
    const t = await api.getTask(currentTask.id);
    setCurrentTask(t);
    setTasks((prev) => prev.map((p) => (p.id === t.id ? t : p)));
  };
  const createTask = async (form: FormData) => {
    const t = await api.createTask(form);
    await refreshTasks();
    setCurrentTask(t);
    return t;
  };
  const deleteTask = async (id: string) => {
    await api.deleteTask(id);
    if (currentTask?.id === id) setCurrentTask(null);
    await refreshTasks();
  };
  const patchCurrent = async (p: { name?: string; goal?: string }) => {
    if (!currentTask) return;
    const t = await api.patchTask(currentTask.id, p);
    setCurrentTask(t);
    setTasks((prev) => prev.map((x) => (x.id === t.id ? t : x)));
  };
  const selectDevice = async (d: string) => {
    const r = await api.setDevice(d);
    setDevice(r.device);
    setDeviceConfigured(r.configured);
  };
  const refreshDevices = async () => {
    const [ds, dg] = await Promise.all([api.devices(), api.getDevice()]);
    setDevices(ds);
    setDevice(dg.device);
    setDeviceConfigured(dg.configured);
  };

  const setCurrent = (t: Task | null) => setCurrentTask(t);

  useEffect(() => {
    (async () => {
      await Promise.all([refreshTasks(), refreshDevices()]);
      setLoading(false);
    })();
  }, []);

  const value: TasksCtx = {
    tasks, currentTask, devices, device, deviceConfigured, loading,
    refreshTasks, refreshCurrent, createTask, deleteTask, setCurrent, patchCurrent, selectDevice, refreshDevices,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTasks() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTasks must be used within TasksProvider");
  return c;
}
