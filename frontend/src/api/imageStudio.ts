import { api, apiUrl } from "./client";
import { ApiError } from "../types/operator";

export type StudioModel = { model_id: string; display_name: string; workflow_file: string; required_custom_nodes: string[] };
export type StudioCapability = { comfyui: string; base_url: string; installation: string; paths: Record<string, string>; generation_available: boolean; api: { reachable: boolean; api_available: boolean; checks: Record<string, { reachable: boolean; http_status: number | null; error?: string }> }; runtime_models: { checkpoints: string[]; unets: string[]; text_encoders: string[]; vaes: string[]; generation_model_files_detected: boolean }; models: StudioModel[]; custom_nodes: { name: string; status: string }[]; supported_workflows: string[]; missing_requirements: { code: string; message: string; node?: string; model_file?: string; workflow_file?: string }[] };
export type StudioPreset = { preset_id: string; name: string; settings: Record<string, string | number> };
export type ImageAsset = { asset_id: string; filename: string; mime_type: string; width: number; height: number; preview_url: string; created_at: string; metadata: Record<string, unknown> };
export type ImageJob = { job_id: string; status: string; progress: number; stage: string; settings: Record<string, unknown>; prompt: string; negative_prompt: string; output_images: ImageAsset[]; error?: { code: string; message: string; http_status?: number; node_errors?: unknown }; created_at: string };

async function createJob(character: File, product: File, settings: Record<string, unknown>) {
  const form = new FormData(); form.append("character_image", character); form.append("product_image", product); form.append("settings", JSON.stringify(settings));
  const requestId = crypto.randomUUID();
  const response = await fetch(`${apiUrl}/image-studio/jobs`, { method: "POST", headers: { "X-Request-ID": requestId }, body: form });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(String(body?.detail || `Image job failed (${response.status})`), response.status, response.headers.get("X-Request-ID") || requestId, body);
  return body as { job_id: string; status: string };
}

export const imageStudioApi = {
  capabilities: () => api<StudioCapability>("/image-studio/capabilities"),
  presets: () => api<StudioPreset[]>("/image-studio/presets"),
  jobs: () => api<ImageJob[]>("/image-studio/jobs?limit=100"),
  createJob,
  regenerate: (jobId: string, sameSeed = false) => api<{ job_id: string; status: string }>(`/image-studio/jobs/${encodeURIComponent(jobId)}/regenerate?same_seed=${sameSeed}`, { method: "POST" }),
  deleteAsset: (assetId: string) => api<void>(`/image-studio/assets/${encodeURIComponent(assetId)}`, { method: "DELETE" }),
  previewUrl: (asset: ImageAsset) => `${apiUrl}${asset.preview_url}`,
};
