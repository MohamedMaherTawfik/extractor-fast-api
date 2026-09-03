# ComfyUI production workflows

These JSON files define the API-format workflow boundary used by EMY. They are
deliberately small deployment templates because node packs and checkpoint names
differ between GPU installations.

On the dedicated GPU machine:

1. Install ComfyUI and the nodes/checkpoints required by the selected model.
2. Build and validate the image-to-video graph in ComfyUI.
3. Export it with **Save (API Format)**.
4. Replace the corresponding JSON file while retaining the configured injection
   node IDs, or update `configs/video_generation.yaml` to match the exported IDs.
5. Set `EMY_COMFYUI_BASE_URL` when ComfyUI is not at `127.0.0.1:8188`.

EMY uploads character references through `/upload/image`, submits graphs through
`/prompt`, polls `/history` and `/queue`, and retrieves outputs through `/view`.
