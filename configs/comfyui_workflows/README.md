# ComfyUI video workflow templates (UNVERIFIED)

These JSON files are deliberately small, **UNVERIFIED** deployment templates.
They are not production workflows and Video Studio will never report them as
ready merely because they exist. Their node IDs, class types, inputs, and model
values must not be assumed to work on another ComfyUI installation.

On the dedicated GPU machine:

1. Install ComfyUI and the nodes/checkpoints required by the selected model.
2. Build and validate the image-to-video graph in ComfyUI.
3. Export it with **Save (API Format)**.
4. Replace the corresponding JSON file and update every mapping in
   `configs/video_generation.yaml` to the exported node IDs and inputs.
5. Add only actual model filenames and required custom `class_type` values
   discovered by that runtime; then set `enabled: true` and `verified: true`.
5. Set `EMY_COMFYUI_BASE_URL` when ComfyUI is not at `127.0.0.1:8188`.

EMY uploads character references through `/upload/image`, submits graphs through
`/prompt`, polls `/history` and `/queue`, and retrieves outputs through `/view`.
