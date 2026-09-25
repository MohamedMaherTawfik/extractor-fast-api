import { api, apiUrl } from "./client";
import { ApiError } from "../types/operator";

export type VideoModel = { model_id: string; display_name: string; enabled: boolean; verified?: boolean; available?: boolean; fps: number; max_duration_seconds: number; aspect_ratios: string[] };
export type VideoRecipe = { recipe_id: string; name: string; camera_style: string; lighting: string; colors: string; environment: string; realism_level: string; motion_style: string };
export type StudioConfig = { version: string; provider: string; comfyui_configured: boolean; comfyui?: string; generation_available?: boolean; default_model: string; models: VideoModel[]; configured_models?: VideoModel[]; missing_requirements?: { code: string; message: string }[]; recipes: VideoRecipe[]; worker: { concurrency: number; active_jobs: string[] } };
export type Character = { character_id: string; name: string; version: number; reference_image: string; identity_data: Record<string, unknown>; style_profile: Record<string, unknown>; recurring_attributes: string[]; negative_constraints: string[]; updated_at: string };
export type VideoAsset = { asset_id: string; version: number; preview_url: string; saved: boolean; filename: string; created_at: string; metadata: Record<string, unknown> };
export type VideoJob = { job_id: string; batch_id?: string; status: string; progress: number; stage: string; request: Record<string, unknown>; prompt_package?: Record<string, unknown>; model?: { model_id: string; display_name: string }; final_video?: VideoAsset; error?: { code: string; message: string; stage?: string; http_status?: number; node_errors?: unknown }; created_at: string };

async function uploadCharacter(form: FormData): Promise<Character> {
  const requestId = crypto.randomUUID();
  const response = await fetch(`${apiUrl}/video-studio/characters`, { method: "POST", headers: { "X-Request-ID": requestId }, body: form });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(String(body?.detail || `Upload failed (${response.status})`), response.status, response.headers.get("X-Request-ID") || requestId, body);
  return body as Character;
}

export const videoStudioApi = {
  config: () => api<StudioConfig>("/video-studio/config"),
  characters: () => api<Character[]>("/video-studio/characters"),
  uploadCharacter,
  jobs: () => api<VideoJob[]>("/video-studio/jobs?limit=100"),
  generate: (payload: Record<string, unknown>) => api<VideoJob>("/video-studio/jobs", { method: "POST", body: JSON.stringify(payload) }),
  batch: (payload: Record<string, unknown>) => api<{ batch_id: string; total: number; job_ids: string[] }>("/video-studio/batches", { method: "POST", body: JSON.stringify(payload) }),
  retry: (jobId: string) => api<VideoJob>(`/video-studio/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" }),
  save: (assetId: string) => api<VideoAsset>(`/video-studio/assets/${encodeURIComponent(assetId)}/save`, { method: "POST" }),
  previewUrl: (asset: VideoAsset) => `${apiUrl}${asset.preview_url}`,
};
