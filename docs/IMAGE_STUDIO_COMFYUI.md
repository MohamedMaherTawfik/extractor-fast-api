# Image Studio ComfyUI runtime contract

Image Studio is application-ready but intentionally has no enabled local image
model. This is reported as `APPLICATION_READY` / `RUNTIME_NOT_CONFIGURED`, not
as generation-ready.

Before enabling a model on the GPU machine:

1. Install the selected image model and its required custom `class_type` values.
2. Build and run the intended graph in ComfyUI.
3. Export the successful graph with **Save (API Format)** to
   `configs/comfyui_image_workflows/`.
4. Add an Image Studio model entry with the exact `model_id`, `display_name`,
   `workflow_file`, `model_files`, `required_custom_nodes`, `output_node_ids`,
   and injection targets. Do not use example values or placeholders.
5. Verify `/system_stats`, `/queue`, and `/object_info` at the configured
   `EMY_COMFYUI_BASE_URL`.

The graph must accept positive/negative prompts and the uploaded character and
product references. Width, height, and seed injections are optional. EMY rejects
placeholders, unavailable nodes/model choices, missing inputs, broken links,
invalid output indexes, type mismatches, and outputs without an image path.

The API exposes `GET /image-studio/capabilities`, `/health`, `/models`,
`/options`, and `/presets`. Jobs are rejected before reference storage when
preflight is unavailable.


## Cancellation and recovery

Image Studio persists whether a job was intended to execute. Active executable
jobs can be recovered after a backend restart, while operator-created dry-run
jobs are left untouched. `POST /image-studio/jobs/{job_id}/cancel` requests
cancellation and persisted jobs report `CANCELLED` without being rewritten as a
generic failure.
