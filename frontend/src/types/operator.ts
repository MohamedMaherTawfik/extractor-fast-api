export type HealthState = "ONLINE" | "DEGRADED" | "OFFLINE" | "NOT_CONFIGURED" | "UNKNOWN";
export type ModuleCapability = { enabled: boolean; version?: string; status?: string; mode?: string };
export type Capabilities = {
  app: { name: string; version: string; environment: string };
  modules: Record<string, ModuleCapability>;
  features: Record<string, boolean>;
  privacy_mode: string;
  realtime: { transport: string; recommended_interval_seconds: number };
};
export type WorkspacePage = { workspace: string; items: Record<string, unknown>[]; total: number; offset: number; limit: number };
export type Dashboard = { as_of: string; metrics: Record<string, string | number>; notifications: NotificationItem[] };
export type NotificationItem = { id: string; severity: string; type: string; title: string; created_at: string };
export type SearchResult = { type: string; uid: string; label: string };

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId?: string, public details?: unknown) { super(message); }
}
