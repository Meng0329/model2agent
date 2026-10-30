// REST + SSE client for the Model2Agent V2.0 backend.
import type { DeviceInfo, Task } from "../types";

const API = "/api";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = "";
    try { detail = (await r.json()).detail || ""; } catch { /* noop */ }
    throw new Error(`${r.status} ${detail}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${API}/health`).then(j<{ ok: boolean; model: string; base_url: string }>),

  listTasks: () => fetch(`${API}/tasks`).then(j<Task[]>),
  getTask: (id: string) => fetch(`${API}/tasks/${id}`).then(j<Task>),
  createTask: async (form: FormData) =>
    fetch(`${API}/tasks`, { method: "POST", body: form }).then(j<Task>),
  patchTask: (id: string, body: { name?: string; goal?: string }) =>
    fetch(`${API}/tasks/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Task>),
  deleteTask: (id: string) => fetch(`${API}/tasks/${id}`, { method: "DELETE" }).then(j<{ ok: boolean }>),

  getMessages: (id: string) => fetch(`${API}/tasks/${id}/messages`).then(j<{ messages: unknown[] }>),

  devices: () => fetch(`${API}/devices`).then(j<DeviceInfo[]>),
  getDevice: () => fetch(`${API}/settings/device`).then(j<{ device: string; configured: boolean }>),
  setDevice: (device: string) =>
    fetch(`${API}/settings/device`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ device }) }).then(j<{ device: string; configured: boolean }>),

  listFiles: (id: string) => fetch(`${API}/tasks/${id}/files`).then(j<{ files: unknown[] }>),
  fileContent: (id: string, path: string) =>
    fetch(`${API}/tasks/${id}/files/content?path=${encodeURIComponent(path)}`).then(j<{ path: string; content: string; size: number; is_binary: boolean }>),
  workspaceState: (id: string) => fetch(`${API}/tasks/${id}/workspace/state`).then(j<{ state: string }>),

  previewStatus: (id: string) => fetch(`${API}/tasks/${id}/preview/status`).then(j<{ state: string; url?: string; error?: string }>),
  requestPreview: (id: string) =>
    fetch(`${API}/tasks/${id}/preview/request`, { method: "POST" }).then(j<{ state: string; url?: string; error?: string }>),
  stopPreview: (id: string) => fetch(`${API}/tasks/${id}/preview/stop`, { method: "POST" }).then(j<{ state: string }>),

  exportTask: (id: string) => `${API}/tasks/${id}/export/download`,
  exportStatus: (id: string) => fetch(`${API}/tasks/${id}/export`).then(j<{ docker_status: string; available: boolean }>),
};

export const API_BASE = API;
