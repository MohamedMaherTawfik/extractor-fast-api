# ComfyUI image workflows

This directory intentionally contains no sample production workflow. Add a
workflow only after exporting it from the target ComfyUI installation with
**Save (API Format)**.

For each future entry in `configs/image_studio.yaml`, the workflow must be a
non-empty JSON object whose nodes have `class_type` and `inputs`. Configure the
exact model files, required custom `class_type` values, output node IDs, and injections.
The required injections are `positive_prompt`, `negative_prompt`,
`character_reference`, and `product_reference`; `width`, `height`, and `seed`
are optional and must be configured only when the exported graph exposes them.

At runtime EMY compares the graph against ComfyUI `/object_info`, checks links,
input/output type compatibility, enum choices, configured outputs, placeholders,
and image availability. A workflow is unavailable until those checks pass.
