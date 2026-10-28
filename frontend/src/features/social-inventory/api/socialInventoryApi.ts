import { api, apiUrl } from "../../../api/client";
import type { Capabilities, CreateSource, Overview, SocialItem, SocialRun, SocialSource } from "../types";

const root = "/social-inventory";
const query = (values: Record<string, string | number | undefined>) => { const params = new URLSearchParams(); Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); }); const text = params.toString(); return text ? `?${text}` : ""; };

export const socialInventoryApi = {
  capabilities: () => api<Capabilities>(`${root}/capabilities`), overview: () => api<Overview>(`${root}/overview`), sources: () => api<SocialSource[]>(`${root}/sources`),
  createSource: (body: CreateSource) => api<{ source: SocialSource; run: SocialRun }>(`${root}/sources`, { method: "POST", body: JSON.stringify(body) }),
  sync: (uuid: string) => api<SocialRun>(`${root}/sources/${uuid}/sync`, { method: "POST" }), runs: () => api<SocialRun[]>(`${root}/runs?limit=100`),
  cancel: (uuid: string) => api<SocialRun>(`${root}/runs/${uuid}/cancel`, { method: "POST" }), retry: (uuid: string) => api<SocialRun>(`${root}/runs/${uuid}/retry`, { method: "POST" }),
  items: (values: Record<string, string | number | undefined>) => api<{ items: SocialItem[]; total: number; offset: number; limit: number }>(`${root}/items${query(values)}`),
  item: (uuid: string) => api<SocialItem>(`${root}/items/${uuid}`), research: (body: { source_uuid: string; goal: string; target_count: number }) => api<Record<string, unknown>>(`${root}/research`, { method: "POST", body: JSON.stringify(body) }),
  exportUrl: (format: "csv" | "xlsx" | "json", values: Record<string, string | number | undefined>) => `${apiUrl}${root}/exports/${format}${query(values)}`,
};
