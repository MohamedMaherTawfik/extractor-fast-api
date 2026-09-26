# Video Studio ComfyUI runtime contract

The JSON files under `configs/comfyui_workflows/` are **UNVERIFIED templates**.
They remain disabled and cannot make Video Studio ready. The application starts
normally without ComfyUI or video models.

To enable a real video model:

1. Install the selected model and its required custom nodes on the GPU runtime.
2. Validate the complete graph in ComfyUI, then export it with **Save (API
   Format)**.
3. Configure exact workflow path, model filenames, required class types,
   injection node IDs/inputs, and output node IDs in `video_generation.yaml`.
4. Set both `enabled: true` and `verified: true` only after live
   `/object_info` validation succeeds.

Video Studio requires prompt, negative-prompt, and reference-image injections.
It validates node classes, required inputs, links, output indexes/types, enum
model choices, expected video/image-frame output paths, and placeholders before
`/prompt` whenever possible. Jobs upload the reference, build the workflow,
submit it, poll history, and store durable progress/error/output provenance.

Use `GET /video-studio/capabilities` or `/health` to see `COMFYUI_API_UNAVAILABLE`,
`NO_LOCAL_VIDEO_MODEL`, `NO_VIDEO_WORKFLOW_CONFIGURED`, `INVALID_WORKFLOW`,
`MISSING_CUSTOM_NODE`, `MODEL_FILE_NOT_FOUND`, or `READY`.


Reference uploads are validated by content signature, MIME type, filename extension, file-size limit, and image dimensions before they enter character memory. Runtime request/upload and generation timeouts remain configurable in `configs/video_generation.yaml`.
