"""Load, validate, and inject only explicitly configured image workflows."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from backend.core.exceptions import ConfigurationError
from backend.image_studio.schemas import ImageModelConfig, ImageStudioSettings


RATIO_DIMENSIONS = {
    "1:1": (1024, 1024), "4:5": (832, 1040), "3:4": (768, 1024),
    "2:3": (768, 1152), "9:16": (576, 1024), "16:9": (1024, 576),
    "4:3": (1024, 768), "3:2": (1152, 768), "21:9": (1344, 576),
    "9:21": (576, 1344), "5:4": (1024, 832), "4:1": (1536, 384),
    "1:4": (384, 1536), "2:1": (1536, 768), "1:2": (768, 1536),
}
PLACEHOLDER_MARKERS = {
    "CONFIGURE_ON_GPU_MACHINE", "TODO", "CHANGE_ME", "PLACEHOLDER", "REPLACE_ME",
}


class ImageWorkflowManager:
    def __init__(self, workflows_root: Path) -> None:
        self.workflows_root = workflows_root.resolve()

    def load_and_validate(
        self,
        model: ImageModelConfig,
        object_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._reject_placeholders(model.model_dump(mode="json"), "image model configuration")
        source = (self.workflows_root / model.workflow_file).resolve()
        if not source.is_relative_to(self.workflows_root) or not source.is_file():
            raise ConfigurationError("INVALID_WORKFLOW: configured image workflow was not found")
        try:
            workflow = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError("INVALID_WORKFLOW: image workflow is not valid JSON") from exc
        if not isinstance(workflow, dict) or not workflow:
            raise ConfigurationError("INVALID_WORKFLOW: image workflow must be a non-empty API workflow object")
        self._reject_placeholders(workflow, "image workflow")
        workflow_strings = self._literal_strings(workflow)
        missing_model_refs = [item for item in model.model_files if item not in workflow_strings]
        if missing_model_refs:
            raise ConfigurationError(
                "INVALID_WORKFLOW: configured model files are not referenced by the workflow: "
                + ", ".join(missing_model_refs)
            )
        required = {"positive_prompt", "negative_prompt", "character_reference", "product_reference"}
        missing = required - set(model.injections)
        if missing:
            raise ConfigurationError(f"INVALID_WORKFLOW: missing declared injections: {', '.join(sorted(missing))}")
        for name, target in model.injections.items():
            node = workflow.get(target.node_id)
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                raise ConfigurationError(f"INVALID_WORKFLOW: node {target.node_id} is missing a class_type or inputs")
            if target.input not in node["inputs"]:
                raise ConfigurationError(f"INVALID_WORKFLOW: node {target.node_id} does not expose input {target.input}")
        for node_id in model.output_node_ids:
            node = workflow.get(str(node_id))
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                raise ConfigurationError(f"INVALID_WORKFLOW: output node {node_id} is absent")
        self._validate_static_links(workflow)
        if object_info is not None:
            self._validate_against_comfyui_api(workflow, object_info, model.output_node_ids)
        return workflow

    @staticmethod
    def _reject_placeholders(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for child in value.values():
                ImageWorkflowManager._reject_placeholders(child, location)
        elif isinstance(value, list):
            for child in value:
                ImageWorkflowManager._reject_placeholders(child, location)
        elif isinstance(value, str):
            upper = value.upper()
            if any(marker in upper for marker in PLACEHOLDER_MARKERS):
                raise ConfigurationError(f"INVALID_WORKFLOW: unresolved placeholder in {location}")

    @staticmethod
    def _literal_strings(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for child in value.values():
                found.update(ImageWorkflowManager._literal_strings(child))
        elif isinstance(value, list):
            if not ImageWorkflowManager._is_link(value):
                for child in value:
                    found.update(ImageWorkflowManager._literal_strings(child))
        elif isinstance(value, str):
            found.add(value)
        return found

    @staticmethod
    def _validate_static_links(workflow: dict[str, Any]) -> None:
        for node_id, node in workflow.items():
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                continue
            for input_name, value in node["inputs"].items():
                if ImageWorkflowManager._is_link(value) and str(value[0]) not in workflow:
                    raise ConfigurationError(
                        f"INVALID_WORKFLOW: node {node_id}.{input_name} links to absent node {value[0]}"
                    )

    @staticmethod
    def _validate_against_comfyui_api(
        workflow: dict[str, Any],
        object_info: dict[str, Any],
        output_node_ids: list[str],
    ) -> None:
        """Validate API-format nodes, required inputs, links, and model choices.

        ComfyUI itself remains the authority at ``/prompt``.  This preflight is
        intentionally conservative: it only verifies facts returned by this
        running ComfyUI instance and never infers a node or model name.
        """

        errors: list[str] = []
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                errors.append(f"node {node_id} is not an object")
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str) or not isinstance(inputs, dict):
                errors.append(f"node {node_id} is missing class_type or inputs")
                continue
            specification = object_info.get(class_type)
            if not isinstance(specification, dict):
                errors.append(f"node {node_id} uses unavailable class_type {class_type}")
                continue
            required = specification.get("input", {}).get("required", {})
            if not isinstance(required, dict):
                required = {}
            missing_inputs = set(required) - set(inputs)
            if missing_inputs:
                errors.append(
                    f"node {node_id} is missing required inputs: {', '.join(sorted(missing_inputs))}"
                )
            for input_name, value in inputs.items():
                input_spec = required.get(input_name)
                if input_spec is None:
                    optional = specification.get("input", {}).get("optional", {})
                    input_spec = optional.get(input_name) if isinstance(optional, dict) else None
                if input_spec is None:
                    errors.append(f"node {node_id} does not expose input {input_name}")
                    continue
                ImageWorkflowManager._validate_input(
                    errors=errors,
                    workflow=workflow,
                    object_info=object_info,
                    node_id=str(node_id),
                    input_name=input_name,
                    value=value,
                    input_spec=input_spec,
                )
        for node_id in output_node_ids:
            node = workflow.get(str(node_id))
            spec = object_info.get(node.get("class_type")) if isinstance(node, dict) else None
            if not isinstance(spec, dict):
                continue
            if spec.get("output_node") is False:
                errors.append(f"configured output node {node_id} is not a ComfyUI output node")
            inputs = node.get("inputs", {})
            input_specs = spec.get("input", {}) if isinstance(spec.get("input"), dict) else {}
            available = []
            for group in (input_specs.get("required", {}), input_specs.get("optional", {})):
                if isinstance(group, dict):
                    available.extend(group.get(name) for name in inputs)
            output_types = spec.get("output", [])
            if not any(ImageWorkflowManager._input_type(item) == "IMAGE" for item in available) and "IMAGE" not in output_types:
                errors.append(f"output node {node_id} has no IMAGE input or IMAGE output")
        if errors:
            detail = "; ".join(errors[:20])
            if len(errors) > 20:
                detail += f"; {len(errors) - 20} additional validation errors"
            raise ConfigurationError(f"INVALID_WORKFLOW: {detail}")

    @staticmethod
    def _validate_input(
        *,
        errors: list[str],
        workflow: dict[str, Any],
        object_info: dict[str, Any],
        node_id: str,
        input_name: str,
        value: Any,
        input_spec: Any,
    ) -> None:
        if ImageWorkflowManager._is_link(value):
            source_id, output_index = str(value[0]), value[1]
            source = workflow.get(source_id)
            if not isinstance(source, dict):
                errors.append(f"node {node_id}.{input_name} links to absent node {source_id}")
                return
            source_type = source.get("class_type")
            source_spec = object_info.get(source_type)
            outputs = source_spec.get("output", []) if isinstance(source_spec, dict) else []
            if not isinstance(outputs, list) or output_index < 0 or output_index >= len(outputs):
                errors.append(f"node {node_id}.{input_name} links to invalid output {source_id}[{output_index}]")
                return
            expected_type = ImageWorkflowManager._input_type(input_spec)
            actual_type = outputs[output_index]
            if isinstance(expected_type, str) and isinstance(actual_type, str) and expected_type != actual_type:
                errors.append(
                    f"node {node_id}.{input_name} expects {expected_type} but {source_id}[{output_index}] returns {actual_type}"
                )
            return
        options = ImageWorkflowManager._choice_values(input_spec)
        if options is not None and value not in options:
            errors.append(f"node {node_id}.{input_name} references unavailable value {value!r}")

    @staticmethod
    def _is_link(value: Any) -> bool:
        return (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], (str, int))
            and isinstance(value[1], int)
        )

    @staticmethod
    def _input_type(input_spec: Any) -> str | None:
        if isinstance(input_spec, list) and input_spec and isinstance(input_spec[0], str):
            return input_spec[0]
        return None

    @staticmethod
    def _choice_values(input_spec: Any) -> list[Any] | None:
        if not isinstance(input_spec, list) or not input_spec:
            return None
        values = input_spec[0]
        return values if isinstance(values, list) else None

    def inject(self, workflow: dict[str, Any], *, model: ImageModelConfig, settings: ImageStudioSettings, prompt: str, negative_prompt: str, character_reference: str, product_reference: str, seed: int | None) -> dict[str, Any]:
        compiled = deepcopy(workflow)
        dimensions = RATIO_DIMENSIONS.get(settings.aspect_ratio)
        if not dimensions and {"width", "height"} & set(model.injections):
            raise ConfigurationError(
                "INVALID_WORKFLOW: Custom aspect ratio requires an explicitly configured output size"
            )
        values: dict[str, Any] = {
            "positive_prompt": prompt, "negative_prompt": negative_prompt,
            "character_reference": character_reference, "product_reference": product_reference,
            "seed": seed,
        }
        if dimensions:
            values["width"], values["height"] = dimensions
        for name, target in model.injections.items():
            if name in values and values[name] is not None:
                compiled[target.node_id]["inputs"][target.input] = values[name]
        return compiled
