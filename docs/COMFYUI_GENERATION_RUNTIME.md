# Shared ComfyUI generation runtime

Image Studio and Video Studio use the same configurable ComfyUI base URL
(`EMY_COMFYUI_BASE_URL`, default `http://127.0.0.1:8188`). No local path,
model filename, node class, or workflow is hard-coded by the application.

The connector uses only these ComfyUI operations: `GET /system_stats`,
`GET /queue`, `GET /object_info`, `POST /upload/image`, `POST /prompt`,
`GET /history/{prompt_id}`, `GET /view`, and `POST /interrupt`.

It preserves HTTP status, response body, node errors, workflow stage, prompt
ID, and job ID in persisted job failures. Typical stable codes are
`COMFYUI_API_UNAVAILABLE`, `COMFYUI_UPLOAD_FAILED`,
`COMFYUI_PROMPT_REJECTED`, `COMFYUI_HISTORY_FAILED`,
`COMFYUI_OUTPUT_MISSING`, `COMFYUI_OUTPUT_DOWNLOAD_FAILED`,
`GENERATION_TIMEOUT`, and `GENERATION_CANCELLED`.

The backend never connects to ComfyUI at startup. Capability endpoints are
read-only; actual generation is preflighted before a durable job is made.
Generation, request/upload, and poll intervals are configurable. Cancellation
uses `/interrupt` during polling and does not require an unbounded wait.


Image jobs also support durable cancellation and restart recovery. Jobs created
with execution disabled are never auto-resumed. Video jobs retain their existing
retry/cancel/recovery behavior. Reference uploads are content-validated before
being accepted by either studio.
