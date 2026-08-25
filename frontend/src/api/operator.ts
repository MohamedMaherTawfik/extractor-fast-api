import { api } from "./client";
import type { Capabilities, Dashboard, HealthState, NotificationItem, SearchResult, WorkspacePage } from "../types/operator";

export const operatorApi = {
  capabilities: () => api<Capabilities>("/system/capabilities"),
  health: () => api<Record<string, HealthState>>("/system/health-detail"),
  dashboard: () => api<Dashboard>("/system/dashboard"),
  notifications: () => api<NotificationItem[]>("/system/notifications"),
  search: (q: string) => api<SearchResult[]>(`/system/search?q=${encodeURIComponent(q)}`),
  workspace: (name: string, offset = 0, limit = 50) => api<WorkspacePage>(`/system/workspaces/${name}?offset=${offset}&limit=${limit}`),
  settings: () => api<Record<string, unknown>>("/system/settings"),
};
