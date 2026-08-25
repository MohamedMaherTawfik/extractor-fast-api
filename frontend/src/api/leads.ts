import { api, apiUrl } from "./client";
import type { LeadControl, LeadRun, LeadRunPlan, LeadRunRequest, LeadSource, LeadStats, LeadSummary, Page } from "../types/leads";

const params = (values: Record<string, unknown>) => {
  const result = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== "") result.set(key, String(value)); });
  return result.toString();
};

export const leadApi = {
  sources: () => api<LeadSource[]>("/lead-sources"),
  control: () => api<LeadControl>("/lead-control"),
  stats: () => api<LeadStats>("/lead-stats"),
  createRun: (request: LeadRunRequest) => api<LeadRun | LeadRunPlan>("/lead-runs", { method: "POST", body: JSON.stringify(request) }),
  runs: (offset = 0, limit = 25) => api<Page<LeadRun>>(`/lead-runs?offset=${offset}&limit=${limit}`),
  run: (uid: string) => api<LeadRun>(`/lead-runs/${uid}`),
  controlRun: (uid: string, action: "pause" | "resume" | "cancel" | "retry") => api<LeadRun>(`/lead-runs/${uid}/${action}`, { method: "POST" }),
  leads: (values: Record<string, unknown>) => api<Page<LeadSummary>>(`/leads?${params(values)}`),
  lead: (uid: string) => api<Record<string, unknown>>(`/leads/${uid}`),
  async exportLeads(format: "csv" | "xlsx" | "parquet", filters: Record<string, unknown>) {
    const response = await fetch(`${apiUrl}/leads/export`, { method: "POST", headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() }, body: JSON.stringify({ format, ...filters }) });
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `leads.${format}`; anchor.click(); URL.revokeObjectURL(url);
  },
};

