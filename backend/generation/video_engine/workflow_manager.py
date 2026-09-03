"""Load ComfyUI API workflows and inject EMY generation values."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths
from backend.generation.video_engine.config import VideoModelConfig
from backend.generation.video_engine.schemas import PromptPackage, VideoGenerationRequest


RATIO_DIMENSIONS = {
    "1:1": (1024, 1024), "4:5": (832, 1040),
    "9:16": (576, 1024), "16:9": (1024, 576),
}


class WorkflowManager:
    def __init__(self, workflows_root: Path | None = None) -> None:
        self.workflows_root = (workflows_root or (paths.configs / "comfyui_workflows")).resolve()

    def load(self, model: VideoModelConfig) -> dict[str, Any]:
        source = paths.resolve_under(self.workflows_root, model.workflow_file)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(f"Unable to load ComfyUI workflow for {model.model_id}") from exc
        if not isinstance(payload, dict) or not payload:
            raise ConfigurationError(f"ComfyUI workflow for {model.model_id} must be an API-format object")
        return payload

    def inject(
        self, workflow: dict[str, Any], *, model: VideoModelConfig,
        request: VideoGenerationRequest, prompt: PromptPackage,
        uploaded_reference: str,
    ) -> dict[str, Any]:
        compiled = deepcopy(workflow)
        width, height = RATIO_DIMENSIONS[request.aspect_ratio]
        values: dict[str, Any] = {
            "positive_prompt": prompt.positive_prompt,
            "negative_prompt": prompt.negative_prompt,
            "reference_image": uploaded_reference,
            "width": width, "height": height, "fps": model.fps,
            "num_frames": max(1, round(request.video_duration * model.fps)),
            "duration_seconds": request.video_duration,
            "seed": request.seed if request.seed is not None else -1,
        }
        for name, target in model.injections.items():
            if name not in values:
                continue
            node = compiled.get(target.node_id)
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                raise ConfigurationError(
                    f"Workflow injection target {target.node_id}.inputs is missing for {model.model_id}"
                )
            node["inputs"][target.input] = values[name]
        return compiled
