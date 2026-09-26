"""Discover only configured, verifiable ComfyUI image-generation inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError, ModelCapabilityError
from backend.generation.video_engine.comfyui_connector import ComfyUIConnector
from backend.image_studio.schemas import ImageModelConfig, ImageStudioConfig
from backend.image_studio.workflow import ImageWorkflowManager


class ImageStudioCapabilities:
    """Live, read-only readiness checks for the configured local ComfyUI."""

    def __init__(self, config: ImageStudioConfig) -> None:
        self.config = config

    def report(self) -> dict[str, Any]:
        installation = self._path(self.config.comfyui_install_path)
        custom_nodes = self._custom_nodes(installation)
        api, object_info = self._probe_api()
        runtime_models = self._runtime_model_choices(object_info)
        available_models: list[dict[str, Any]] = []
        model_checks: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []

        if not api["api_available"]:
            missing.append({
                "code": "COMFYUI_API_UNAVAILABLE",
                "message": "ComfyUI is not responding correctly to /system_stats, /queue, and /object_info at the configured base URL.",
            })
        if installation is None:
            missing.append({
                "code": "COMFYUI_INSTALLATION_NOT_CONFIGURED",
                "message": "Set EMY_IMAGE_STUDIO_COMFYUI_INSTALL_PATH in the local .env to enable filesystem verification.",
            })
        if not runtime_models["generation_model_files_detected"]:
            missing.append({
                "code": "NO_LOCAL_IMAGE_MODEL",
                "message": "ComfyUI reports no available checkpoint or UNet model files for local image generation.",
            })

        for model in self.config.models:
            model_missing = self._missing_for_model(model, object_info)
            model_checks.append({
                "model_id": model.model_id,
                "enabled": model.enabled,
                "available": not model_missing and model.enabled and api["api_available"],
                "missing_requirements": model_missing,
            })
            if not model_missing and model.enabled and api["api_available"]:
                available_models.append(self._public_model(model))
            missing.extend(model_missing)

        if not self.config.models:
            missing.append({
                "code": "NO_IMAGE_WORKFLOW_CONFIGURED",
                "message": "No verified image model and ComfyUI API-format workflow are configured for Image Studio.",
            })
        if not available_models:
            missing.append({
                "code": "NO_SUITABLE_IMAGE_MODEL",
                "message": "No configured image model has verified files, nodes, and a valid ComfyUI API workflow.",
            })

        generation_available = bool(api["api_available"] and available_models)
        return {
            "comfyui": "READY" if api["api_available"] else "UNAVAILABLE",
            "base_url": get_settings().comfyui_base_url,
            "installation": str(installation) if installation else "NOT CONFIGURED",
            "paths": {
                "custom_nodes": str(self._custom_nodes_root(installation)) if self._custom_nodes_root(installation) else "NOT FOUND",
                "models": str(self._models_root(installation)) if self._models_root(installation) else "NOT FOUND",
                "workflows": str(self._workflows_root()),
            },
            "api": api,
            "runtime_models": runtime_models,
            "generation_available": generation_available,
            "models": available_models,
            "model_checks": model_checks,
            "custom_nodes": [{"name": item, "status": "INSTALLED"} for item in custom_nodes],
            "supported_workflows": [item["workflow_file"] for item in available_models],
            "missing_requirements": _unique_requirements(missing),
        }

    def model(self, model_id: str | None) -> ImageModelConfig:
        api, object_info = self._probe_api()
        candidates = [model for model in self.config.models if model.enabled]
        if model_id:
            candidates = [model for model in candidates if model.model_id == model_id]
        if not candidates:
            raise ModelCapabilityError("MODEL_NOT_AVAILABLE: no configured image model matches this request")
        model = candidates[0]
        missing = self._missing_for_model(model, object_info)
        if not api["api_available"]:
            missing.append({
                "code": "COMFYUI_API_UNAVAILABLE",
                "message": "ComfyUI API preflight did not pass.",
            })
        if missing:
            details = "; ".join(str(item["code"]) for item in missing)
            code = "MISSING_CUSTOM_NODE" if any(item["code"] == "MISSING_CUSTOM_NODE" for item in missing) else "MODEL_NOT_AVAILABLE"
            raise ModelCapabilityError(f"{code}: {details}")
        return model

    def workflow_root(self) -> Path:
        return self._workflows_root()

    def _probe_api(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
        connector = ComfyUIConnector(get_settings().comfyui_base_url, request_timeout_seconds=5.0)
        try:
            report = connector.runtime_status()
            return {
                "reachable": report["reachable"],
                "api_available": report["api_available"],
                "checks": report["checks"],
            }, report["object_info"] if isinstance(report.get("object_info"), dict) else None
        finally:
            connector.close()

    @staticmethod
    def _runtime_model_choices(object_info: dict[str, Any] | None) -> dict[str, Any]:
        choices = {
            "checkpoints": _node_choices(object_info, "CheckpointLoaderSimple", "ckpt_name"),
            "unets": _node_choices(object_info, "UNETLoader", "unet_name"),
            "text_encoders": _node_choices(object_info, "CLIPLoader", "clip_name"),
            "vaes": _node_choices(object_info, "VAELoader", "vae_name"),
        }
        choices["generation_model_files_detected"] = bool(choices["checkpoints"] or choices["unets"])
        return choices

    def _path(self, configured: str | None) -> Path | None:
        if not configured:
            return None
        candidate = Path(configured).expanduser().resolve()
        return candidate if candidate.is_dir() else None

    def _custom_nodes_root(self, installation: Path | None) -> Path | None:
        candidate = self._path(self.config.custom_nodes_path) if self.config.custom_nodes_path else (installation / "custom_nodes" if installation else None)
        return candidate if candidate and candidate.is_dir() else None

    def _models_root(self, installation: Path | None) -> Path | None:
        candidate = self._path(self.config.models_path) if self.config.models_path else (installation / "models" if installation else None)
        return candidate if candidate and candidate.is_dir() else None

    def _workflows_root(self) -> Path:
        configured = Path(self.config.workflows_path)
        return (configured if configured.is_absolute() else (Path(__file__).resolve().parents[2] / "configs" / configured)).resolve()

    def _custom_nodes(self, installation: Path | None) -> list[str]:
        root = self._custom_nodes_root(installation)
        if not root:
            return []
        return sorted(item.name for item in root.iterdir() if item.is_dir() and item.name != "__pycache__")

    def _missing_for_model(
        self,
        model: ImageModelConfig,
        object_info: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        installation = self._path(self.config.comfyui_install_path)
        models_root = self._models_root(installation)
        missing: list[dict[str, Any]] = []
        if not models_root:
            missing.append({"code": "MODEL_FILES_ROOT_NOT_FOUND", "message": "The configured ComfyUI models directory was not found."})
        else:
            for relative in model.model_files:
                candidate = (models_root / relative).resolve()
                if not candidate.is_relative_to(models_root.resolve()) or not candidate.is_file():
                    missing.append({"code": "MODEL_FILE_NOT_FOUND", "model_file": relative, "message": f"Required model file is missing: {relative}"})
        if isinstance(object_info, dict):
            for class_type in model.required_custom_nodes:
                if class_type not in object_info:
                    missing.append({
                        "code": "MISSING_CUSTOM_NODE",
                        "node": class_type,
                        "message": f"Required ComfyUI class_type is unavailable: {class_type}",
                    })
        try:
            ImageWorkflowManager(self._workflows_root()).load_and_validate(model, object_info)
        except ConfigurationError as exc:
            missing.append({"code": "INVALID_WORKFLOW", "workflow_file": model.workflow_file, "message": str(exc)})
        return missing

    @staticmethod
    def _public_model(model: ImageModelConfig) -> dict[str, Any]:
        return {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "workflow_file": model.workflow_file,
            "required_custom_nodes": model.required_custom_nodes,
        }


def _node_choices(object_info: dict[str, Any] | None, node_name: str, input_name: str) -> list[str]:
    if not isinstance(object_info, dict):
        return []
    node = object_info.get(node_name)
    if not isinstance(node, dict):
        return []
    inputs = node.get("input", {}).get("required", {})
    if not isinstance(inputs, dict):
        return []
    specification = inputs.get(input_name)
    if not isinstance(specification, list) or not specification or not isinstance(specification[0], list):
        return []
    return [str(value) for value in specification[0]]


def _unique_requirements(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in items:
        key = (item.get("code"), item.get("node"), item.get("model_file"), item.get("workflow_file"), item.get("message"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
