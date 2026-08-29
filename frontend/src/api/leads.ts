import { api, apiUrl } from "./client";
import type { LeadControl, LeadRun, LeadRunPlan, LeadRunRequest, LeadSource, LeadStats, LeadSummary, Page } from "../types/leads";

const params = (values: Record<string, unknown>) => {
  const result = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== "") result.set(key, String(value)); });
  return result.toString();
};

const arrayOrEmpty = <T>(value: T[] | null | undefined): T[] => Array.isArray(value) ? value : [];

type LeadRunPlanWire = Omit<Partial<LeadRunPlan>, "enabled_sources" | "governorates" | "segments" | "missing_credentials" | "warnings"> & {
  dry_run: true;
  enabled_sources?: string[] | null;
  governorates?: string[] | null;
  segments?: string[] | null;
  missing_credentials?: string[] | null;
  warnings?: string[] | null;
};

export function normalizeLeadRunPlan(value: LeadRunPlanWire): LeadRunPlan {
  return {
    dry_run: true,
    enabled_sources: arrayOrEmpty(value.enabled_sources),
    governorates: arrayOrEmpty(value.governorates),
    segments: arrayOrEmpty(value.segments),
    keyword_count: value.keyword_count ?? 0,
    planned_jobs: value.planned_jobs ?? 0,
    missing_credentials: arrayOrEmpty(value.missing_credentials),
    warnings: arrayOrEmpty(value.warnings),
  };
}

export const leadApi = {
  sources: () => api<LeadSource[]>("/lead-sources"),
  control: () => api<LeadControl>("/lead-control"),
  stats: () => api<LeadStats>("/lead-stats"),
  async createRun(request: LeadRunRequest): Promise<LeadRun | LeadRunPlan> {
    const result = await api<LeadRun | LeadRunPlanWire>("/lead-runs", { method: "POST", body: JSON.stringify(request) });
    if ((result as Partial<LeadRunPlan>).dry_run === true) {
      return normalizeLeadRunPlan(result as LeadRunPlanWire);
    }
    return result as LeadRun;
  },
  runs: (offset = 0, limit = 25) => api<Page<LeadRun>>(`/lead-runs?offset=${offset}&limit=${limit}`),
  run: (uid: string) => api<LeadRun>(`/lead-runs/${uid}`),
  controlRun: (uid: string, action: "pause" | "resume" | "cancel" | "retry") => api<LeadRun>(`/lead-runs/${uid}/${action}`, { method: "POST" }),
  leads: (values: Record<string, unknown>) => api<Page<LeadSummary>>(`/leads?${params(values)}`),
  lead: (uid: string) => api<Record<string, unknown>>(`/leads/${uid}`),
  async exportLeads(format: "csv" | "xlsx" | "parquet", filters: Record<string, unknown>) {
    const response = await fetch(`${apiUrl}/leads/export`, { method: "POST", headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() }, body: JSON.stringify({ format, ...filters }) });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(String(body?.detail || `Export failed (${response.status})`));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `leads.${format}`; anchor.click(); URL.revokeObjectURL(url);
  },
};

