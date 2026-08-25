import { ApiError } from "../types/operator";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT_MS || 12000);

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT);
  const requestId = crypto.randomUUID();
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-Request-ID": requestId, ...options.headers },
    });
    const returnedId = response.headers.get("X-Request-ID") || requestId;
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const message = body?.detail?.message || body?.detail || body?.message || `Request failed (${response.status})`;
      throw new ApiError(String(message), response.status, returnedId, body);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new ApiError("Backend request timed out", 0, requestId);
    throw new ApiError("Backend is unavailable", 0, requestId);
  } finally {
    clearTimeout(timer);
  }
}

export const apiUrl = API_URL;
