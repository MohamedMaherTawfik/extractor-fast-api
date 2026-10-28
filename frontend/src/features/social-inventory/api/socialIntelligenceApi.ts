import { api, apiUrl } from "../../../api/client";
import type {
  AnalysisJob,
  CompleteAnalysis,
  CreativeRecommendation,
  CreatorIntelligence,
  ExcelExportJob,
  HookAnalysis,
  Transcript,
} from "../intelligenceTypes";

const root = "/social-intelligence";

export const socialIntelligenceApi = {
  analyze: (itemUuid: string, force = false) =>
    api<AnalysisJob>(`${root}/analyze/${itemUuid}?force_reprocess=${force}`, {
      method: "POST",
    }),

  analyzeBatch: (itemUuids: string[], force = false) =>
    api<AnalysisJob[]>(`${root}/analyze/batch`, {
      method: "POST",
      body: JSON.stringify({ item_uuids: itemUuids, force_reprocess: force }),
    }),

  jobs: (status?: string) =>
    api<AnalysisJob[]>(`${root}/jobs${status ? `?status=${status}` : ""}`),

  job: (jobUuid: string) => api<AnalysisJob>(`${root}/jobs/${jobUuid}`),

  retry: (jobUuid: string) =>
    api<AnalysisJob>(`${root}/jobs/${jobUuid}/retry`, { method: "POST" }),

  analysis: (itemUuid: string) =>
    api<CompleteAnalysis>(`${root}/items/${itemUuid}`),

  creator: (platform: string, username: string) =>
    api<CreatorIntelligence>(`${root}/creators/${platform}/${username}`),

  generateCreative: (params: {
    item_uuid?: string;
    creator_username?: string;
    output_type: string;
    target_platform?: string;
    target_audience?: string;
    target_duration?: string;
    target_language?: string;
    topic_context?: string;
  }) =>
    api<CreativeRecommendation[]>(`${root}/creative/generate`, {
      method: "POST",
      body: JSON.stringify(params),
    }),

  listCreative: (itemUuid: string) =>
    api<CreativeRecommendation[]>(`${root}/creative/items/${itemUuid}`),

  createExcelExport: (params: {
    scope: string;
    item_uuids?: string[];
    creator_username?: string;
    filters?: Record<string, unknown>;
  }) =>
    api<ExcelExportJob>(`${root}/exports/excel`, {
      method: "POST",
      body: JSON.stringify(params),
    }),

  downloadExportUrl: (exportUuid: string) =>
    `${apiUrl}${root}/exports/excel/${exportUuid}/download`,

  streamExportUrl: (params?: { creator?: string; scope?: string }) => {
    const q = new URLSearchParams();
    if (params?.creator) q.set("creator_username", params.creator);
    if (params?.scope) q.set("scope", params.scope);
    const qs = q.toString();
    return `${apiUrl}${root}/exports/excel/stream${qs ? `?${qs}` : ""}`;
  },
};
