# EMY Local AI Video Generation Engine

## Scope

EMY Video Studio is an isolated extension under
`backend/generation/video_engine`. It does not replace or modify the existing
contract-first multimodal Generation Engine. The module targets a dedicated GPU
machine and contains no development-device hardware probing.

## Runtime flow

1. The operator stores a JPEG, PNG, or WebP character reference plus structured
   identity, style, recurring-attribute, and negative-constraint memory.
2. A fixed recipe combines the master prompt with the short creative idea,
   camera motion, style, duration, and output ratio.
3. Character identity fields and the reference checksum become immutable job
   metadata and explicit positive/negative prompt constraints.
4. The model router selects an enabled workflow for Wan Video, Hunyuan Video,
   AnimateDiff, or Stable Video Diffusion.
5. EMY uploads the reference to ComfyUI, injects prompt/image/dimensions/frame
   count/FPS/seed, submits `/prompt`, tracks `/queue` and `/history`, and fetches
   the final media through `/view`.
6. The bounded GPU worker stores progress durably. The asset manager saves the
   video, prompt package, script, identity checksum, model/workflow provenance,
   ComfyUI prompt ID, checksum, version, and metadata in the EMY Asset Library.

## Dedicated GPU deployment

Set up the runtime on the GPU host; no GPU configuration is required on the
developer workstation.

1. Install ComfyUI, Video Helper Suite (or the video output node used by the
   chosen graph), the chosen model's required nodes, and its checkpoint files.
2. Validate an image-to-video graph directly in ComfyUI.
3. Export the graph using **Save (API Format)** into
   `configs/comfyui_workflows/<model>.json`.
4. Match the exported prompt, negative prompt, Load Image, dimensions, frame
   count, FPS, seed, and output node IDs in `configs/video_generation.yaml`.
5. Set `EMY_COMFYUI_BASE_URL`, for example
   `http://127.0.0.1:8188` when EMY and ComfyUI share the GPU machine.
6. Keep ComfyUI bound to loopback or a trusted private network. No credential is
   stored in the repository.
7. Start the existing EMY FastAPI and desktop runtimes normally. Open
   **AI Video Studio** in the desktop sidebar.

The included JSON files are API injection templates, not a promise that a
particular third-party custom-node pack uses the same class names. Production
deployments replace them with graphs exported from the installed GPU runtime;
no Python code change is needed.

## Configuration

`configs/video_generation.yaml` controls:

- the default model and enabled models;
- per-model workflow, FPS, maximum duration, ratios, and reference support;
- arbitrary ComfyUI node/input injection mappings and output node IDs;
- GPU worker concurrency, polling, timeout, and upload size;
- reusable fixed master-prompt recipes.

Use worker concurrency `1` unless the GPU deployment was deliberately sized and
tested for concurrent model execution.

## API

- `GET /video-studio/config`
- `POST/GET /video-studio/characters`
- `POST/GET /video-studio/jobs`
- `GET /video-studio/jobs/{job_id}`
- `POST /video-studio/jobs/{job_id}/run|retry|cancel`
- `POST /video-studio/batches`
- `GET /video-studio/batches` and `GET /video-studio/batches/{batch_id}`
- `GET /video-studio/assets`
- `GET /video-studio/assets/{asset_id}`
- `GET /video-studio/assets/{asset_id}/content`
- `POST /video-studio/assets/{asset_id}/save`

`POST /video-studio/batches` accepts up to 120 content-calendar items. Each item
can carry its calendar ID and publish time and receives its own script, compiled
prompt, queue job, and asset provenance.

## Persistence and privacy

- Character memory: `data/assets/references/video_characters/`
- Durable jobs and batches: `data/video_generation/`
- Generated video assets: `data/assets/generated/video_studio/`

All persisted paths are project-relative. Character images and prompts remain
local to EMY and the configured ComfyUI host. Assets are checksummed and stored
with numbered version records; save/library state is tracked separately in the
record metadata.
