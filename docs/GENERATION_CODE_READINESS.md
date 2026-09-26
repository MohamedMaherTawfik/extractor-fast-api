# EMY Image + Video Generation — Code Readiness

Status: **APPLICATION_READY / RUNTIME_NOT_CONFIGURED**

The application-side generation stack is prepared to run without ComfyUI, without models,
and without production workflows. Runtime readiness is deliberately withheld until the real
ComfyUI installation proves all required capabilities through `/object_info` and the configured
workflow/model contracts.

## Image Studio

Application code includes reference validation and storage, prompt/preset generation, schema-derived
creative options, persistent jobs, restart recovery, cancellation, regeneration, seed reuse,
capability checks, strict API-workflow validation, output validation, asset persistence, and detailed
ComfyUI error preservation.

Still external/runtime-only:

1. Select/install the real image model files.
2. Install the exact custom nodes/class types required by that graph.
3. Export the working image graph from the target ComfyUI installation with **Save (API Format)**
   and configure the exact injections/output nodes in `configs/image_studio.yaml`.

## Video Studio

Application code includes content-validated character references, persistent jobs/batches/assets,
retry/cancel/restart recovery, prompt packages, model routing, capability checks, strict API-workflow
validation, output-content validation, configurable long-running timeouts, and detailed ComfyUI error
preservation.

The bundled video JSON files remain disabled, unverified templates and cannot become generation-ready
merely because they exist.

Still external/runtime-only:

1. Select/install the real video model files.
2. Install the exact custom nodes/class types required by that graph.
3. Export the working video graph from the target ComfyUI installation with **Save (API Format)**
   and configure exact model files, injections and output nodes in `configs/video_generation.yaml`.

## Shared ComfyUI contract

The shared connector supports:

- `GET /system_stats`
- `GET /queue`
- `GET /object_info`
- `POST /upload/image`
- `POST /prompt`
- `GET /history/{prompt_id}`
- `GET /view`
- `POST /interrupt`

The main backend can import and start while ComfyUI is offline. Capability endpoints report runtime
unavailability instead of crashing application startup.
