"""Load, validate, and inject real ComfyUI API-format video workflows."""

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
PLACEHOLDER_MARKERS = {
    "CONFIGURE_ON_GPU_MACHINE", "TODO", "CHANGE_ME", "PLACEHOLDER", "REPLACE_ME",
}
SUPPORTED_INJECTIONS = {
    "positive_prompt", "negative_prompt", "reference_image", "width", "height", "fps",
    "num_frames", "duration_seconds", "seed",
}


class WorkflowManager:
    def __init__(self, workflows_root: Path | None = None) -> None:
        self.workflows_root = (workflows_root or (paths.configs / "comfyui_workflows")).resolve()

    def load(self, model: VideoModelConfig) -> dict[str, Any]:
        source = paths.resolve_under(self.workflows_root, model.workflow_file)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(f"INVALID_WORKFLOW: unable to load ComfyUI workflow for {model.model_id}") from exc
        if not isinstance(payload, dict) or not payload:
            raise ConfigurationError(f"INVALID_WORKFLOW: ComfyUI workflow for {model.model_id} must be a non-empty API object")
        return payload

    def load_and_validate(
        self, model: VideoModelConfig, object_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._reject_placeholders(model.model_dump(mode="json"), "video model configuration")
        workflow = self.load(model)
        self._reject_placeholders(workflow, "video workflow")
        workflow_strings = self._literal_strings(workflow)
        missing_model_refs = [item for item in model.model_files if item not in workflow_strings]
        if missing_model_refs:
            raise ConfigurationError(
                "INVALID_WORKFLOW: configured model files are not referenced by the workflow: "
                + ", ".join(missing_model_refs)
            )
        self._validate_static(workflow, model)
        if object_info is not None:
            self._validate_live(workflow, model, object_info)
        return workflow

    @staticmethod
    def _reject_placeholders(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for child in value.values():
                WorkflowManager._reject_placeholders(child, location)
        elif isinstance(value, list):
            for child in value:
                WorkflowManager._reject_placeholders(child, location)
        elif isinstance(value, str) and any(marker in value.upper() for marker in PLACEHOLDER_MARKERS):
            raise ConfigurationError(f"INVALID_WORKFLOW: unresolved placeholder in {location}")

    @staticmethod
    def _validate_static(workflow: dict[str, Any], model: VideoModelConfig) -> None:
        errors: list[str] = []
        required_injections = {"positive_prompt", "negative_prompt"}
        if model.supports_image_reference:
            required_injections.add("reference_image")
        missing = required_injections - set(model.injections)
        if missing:
            errors.append(f"missing declared injections: {', '.join(sorted(missing))}")
        unknown = set(model.injections) - SUPPORTED_INJECTIONS
        if unknown:
            errors.append(f"unknown injection names: {', '.join(sorted(unknown))}")
        for node_id, node in workflow.items():
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                errors.append(f"node {node_id} is missing class_type or inputs")
                continue
            for input_name, value in node["inputs"].items():
                if WorkflowManager._is_link(value) and str(value[0]) not in workflow:
                    errors.append(f"node {node_id}.{input_name} links to absent node {value[0]}")
        for name, target in model.injections.items():
            node = workflow.get(str(target.node_id))
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                errors.append(f"injection {name} targets absent node {target.node_id}")
            elif target.input not in node["inputs"]:
                errors.append(f"injection {name} targets missing input {target.node_id}.{target.input}")
        for node_id in model.output_node_ids:
            node = workflow.get(str(node_id))
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                errors.append(f"configured output node {node_id} is absent")
        if errors:
            raise ConfigurationError(f"INVALID_WORKFLOW: {'; '.join(errors[:20])}")

    @staticmethod
    def _validate_live(workflow: dict[str, Any], model: VideoModelConfig, object_info: dict[str, Any]) -> None:
        errors: list[str] = []
        for required_class in model.required_custom_nodes:
            if required_class not in object_info:
                errors.append(f"required custom node/class_type {required_class} is unavailable")
        used_model_choices: set[str] = set()
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = node["class_type"]
            inputs = node["inputs"]
            spec = object_info.get(class_type)
            if not isinstance(spec, dict):
                errors.append(f"node {node_id} uses unavailable class_type {class_type}")
                continue
            input_spec = spec.get("input") if isinstance(spec.get("input"), dict) else {}
            required = input_spec.get("required") if isinstance(input_spec.get("required"), dict) else {}
            optional = input_spec.get("optional") if isinstance(input_spec.get("optional"), dict) else {}
            missing = set(required) - set(inputs)
            if missing:
                errors.append(f"node {node_id} is missing required inputs: {', '.join(sorted(missing))}")
            for input_name, value in inputs.items():
                declared = required.get(input_name, optional.get(input_name))
                if declared is None:
                    errors.append(f"node {node_id} does not expose input {input_name}")
                    continue
                choices = WorkflowManager._choice_values(declared)
                if choices is not None:
                    if not WorkflowManager._is_link(value):
                        if value not in choices:
                            errors.append(f"node {node_id}.{input_name} references unavailable value {value!r}")
                        elif isinstance(value, str):
                            used_model_choices.add(value)
                if WorkflowManager._is_link(value):
                    source_id, output_index = str(value[0]), value[1]
                    source = workflow.get(source_id)
                    source_spec = object_info.get(source.get("class_type")) if isinstance(source, dict) else None
                    outputs = source_spec.get("output", []) if isinstance(source_spec, dict) else []
                    if not isinstance(outputs, list) or output_index < 0 or output_index >= len(outputs):
                        errors.append(f"node {node_id}.{input_name} links to invalid output {source_id}[{output_index}]")
                    else:
                        expected = WorkflowManager._input_type(declared)
                        actual = outputs[output_index]
                        if isinstance(expected, str) and isinstance(actual, str) and expected != actual:
                            errors.append(f"node {node_id}.{input_name} expects {expected} but {source_id}[{output_index}] returns {actual}")
        for model_file in model.model_files:
            if model_file not in used_model_choices:
                errors.append(f"configured model file is not selected by this workflow/runtime: {model_file}")
        for output_id in model.output_node_ids:
            node = workflow.get(str(output_id))
            spec = object_info.get(node.get("class_type")) if isinstance(node, dict) else None
            if not isinstance(spec, dict):
                continue
            if spec.get("output_node") is False:
                errors.append(f"configured output node {output_id} is not a ComfyUI output node")
            input_spec = spec.get("input") if isinstance(spec.get("input"), dict) else {}
            available = []
            for group in (input_spec.get("required", {}), input_spec.get("optional", {})):
                if isinstance(group, dict):
                    available.extend(group.get(name) for name in node.get("inputs", {}))
            output_types = spec.get("output", [])
            compatible = {"IMAGE", "VIDEO", "LATENT", "AUDIO"}
            if not any(WorkflowManager._input_type(item) in compatible for item in available) and not any(item in compatible for item in output_types):
                errors.append(f"output node {output_id} has no video-compatible or image-frame input/output")
        if errors:
            raise ConfigurationError(f"INVALID_WORKFLOW: {'; '.join(errors[:20])}")

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
            node = compiled.get(target.node_id)
            if name not in values or not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                raise ConfigurationError(f"INVALID_WORKFLOW: injection target {target.node_id}.inputs is missing for {model.model_id}")
            node["inputs"][target.input] = values[name]
        return compiled

    @staticmethod
    def _literal_strings(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for child in value.values():
                found.update(WorkflowManager._literal_strings(child))
        elif isinstance(value, list):
            if not WorkflowManager._is_link(value):
                for child in value:
                    found.update(WorkflowManager._literal_strings(child))
        elif isinstance(value, str):
            found.add(value)
        return found

    @staticmethod
    def _is_link(value: Any) -> bool:
        return isinstance(value, list) and len(value) == 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int)

    @staticmethod
    def _input_type(specification: Any) -> str | None:
        return specification[0] if isinstance(specification, list) and specification and isinstance(specification[0], str) else None

    @staticmethod
    def _choice_values(specification: Any) -> list[Any] | None:
        if not isinstance(specification, list) or not specification or not isinstance(specification[0], list):
            return None
        return specification[0]
