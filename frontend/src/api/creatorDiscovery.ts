import { api, apiUrl } from "./client";
import type { Candidate, ConnectorCapability, CreatorDetail, CreatorSummary, DiscoveryPlatform, DiscoveryRequest, DiscoveryRun, MetaConnectionStatus, Page } from "../types/creatorDiscovery";

async function download(path: string, payload: Record<string, unknown>, filename: string) {
  const response = await fetch(`${apiUrl}${path}`, { method: "POST", headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}

export const creatorDiscoveryApi = {
  connectors: () => api<ConnectorCapability[]>("/creator-discovery/connectors"),
  metaStatus: () => api<MetaConnectionStatus>("/creator-discovery/meta/status"),
  validateMeta: () => api<MetaConnectionStatus>("/creator-discovery/meta/validate", { method: "POST" }),
  industries: () => api<{ code: string; name: string; aliases: string[] }[]>("/creator-discovery/industries"),
  createRun: (payload: DiscoveryRequest) => api<DiscoveryRun>("/creator-discovery/runs", { method: "POST", body: JSON.stringify(payload) }),
  importRun: async (file: File, payload: Omit<DiscoveryRequest, "inputs">) => {
    const form = new FormData(); form.append("file", file); form.append("platforms", JSON.stringify(payload.platforms));
    form.append("analyze_content", String(payload.analyze_content)); form.append("resolve_cross_platform_identity", String(payload.resolve_cross_platform_identity));
    form.append("update_existing_profiles", String(payload.update_existing_profiles)); form.append("content_sample_size", String(payload.content_sample_size)); form.append("execute", String(payload.execute));
    const response = await fetch(`${apiUrl}/creator-discovery/runs/import`, { method: "POST", headers: { "X-Request-ID": crypto.randomUUID() }, body: form });
    const body = await response.json().catch(() => null); if (!response.ok) throw new Error(body?.detail || `Import failed (${response.status})`); return body as DiscoveryRun;
  },
  runs: (offset = 0) => api<Page<DiscoveryRun>>(`/creator-discovery/runs?offset=${offset}&limit=50`),
  run: (uid: string) => api<DiscoveryRun>(`/creator-discovery/runs/${encodeURIComponent(uid)}`),
  runAction: (uid: string, action: "pause" | "resume" | "retry" | "cancel") => api<DiscoveryRun>(`/creator-discovery/runs/${encodeURIComponent(uid)}/${action}`, { method: "POST" }),
  candidates: (offset = 0, status = "PENDING") => api<Page<Candidate>>(`/creator-discovery/candidates?offset=${offset}&limit=50&review_status=${encodeURIComponent(status)}`),
  candidate: (uid: string) => api<Candidate>(`/creator-discovery/candidates/${encodeURIComponent(uid)}`),
  confirm: (uid: string, action: "THIS_IS_THE_ACCOUNT" | "MERGE" | "KEEP_SEPARATE" = "THIS_IS_THE_ACCOUNT", creatorUid?: string) => api<CreatorDetail>(`/creator-discovery/candidates/${encodeURIComponent(uid)}/confirm`, { method: "POST", body: JSON.stringify({ action, creator_uid: creatorUid || null }) }),
  reject: (uid: string) => api<Candidate>(`/creator-discovery/candidates/${encodeURIComponent(uid)}/reject`, { method: "POST" }),
  creators: (params: URLSearchParams) => api<Page<CreatorSummary>>(`/creator-discovery/creators?${params}`),
  creator: (uid: string) => api<CreatorDetail>(`/creator-discovery/creators/${encodeURIComponent(uid)}`),
  updateCreator: (uid: string, payload: Record<string, unknown>) => api<CreatorDetail>(`/creator-discovery/creators/${encodeURIComponent(uid)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  refresh: (uid: string, platforms: DiscoveryPlatform[] = []) => api<CreatorDetail>(`/creator-discovery/creators/${encodeURIComponent(uid)}/refresh`, { method: "POST", body: JSON.stringify({ platforms, analyze_content: true, content_sample_size: 10 }) }),
  export: (format: "csv" | "xlsx", extended: boolean) => download("/creators/export", { format, extended }, `creator_discovery.${format}`),
};
