"""Video-model routing and live ComfyUI capability checks."""

from __future__ import annotations

from typing import Any, Callable

from backend.core.exceptions import ConfigurationError, ModelCapabilityError
from backend.generation.video_engine.comfyui_connector import ComfyUIConnector
from backend.generation.video_engine.config import VideoEngineConfig, VideoModelConfig
from backend.generation.video_engine.schemas import VideoGenerationRequest
from backend.generation.video_engine.workflow_manager import WorkflowManager


ConnectorFactory = Callable[[], ComfyUIConnector]


class VideoStudioCapabilities:
    """Read-only preflight which never treats a JSON template as runnable."""

    def __init__(
        self, config: VideoEngineConfig, workflows: WorkflowManager,
        connector_factory: ConnectorFactory,
    ) -> None:
        self.config = config
        self.workflows = workflows
        self.connector_factory = connector_factory

    def report(self) -> dict[str, Any]:
        connector = self.connector_factory()
        try:
            runtime = connector.runtime_status()
        finally:
            close = getattr(connector, "close", None)
            if callable(close):
                close()
        object_info = runtime.get("object_info") if isinstance(runtime.get("object_info"), dict) else None
        api_available = bool(runtime.get("api_available"))
        missing: list[dict[str, str]] = []
        if not api_available:
            missing.append({
                "code": "COMFYUI_API_UNAVAILABLE",
                "message": "ComfyUI did not pass /system_stats, /queue, and /object_info preflight.",
            })
        checks: list[dict[str, Any]] = []
        available: list[VideoModelConfig] = []
        for model in self.config.models:
            model_missing = self._missing_for_model(model, object_info)
            if not model.enabled:
                model_missing.append({"code": "NO_VIDEO_WORKFLOW_CONFIGURED", "message": "Model is disabled in configuration."})
            if not model.verified:
                model_missing.append({"code": "NO_VIDEO_WORKFLOW_CONFIGURED", "message": "Workflow is an unverified template, not a validated runtime workflow."})
            ready = api_available and model.enabled and model.verified and not model_missing
            checks.append({
                "model_id": model.model_id,
                "enabled": model.enabled,
                "verified": model.verified,
                "available": ready,
                "missing_requirements": _unique(model_missing),
            })
            if ready:
                available.append(model)
            missing.extend(model_missing)
        if not self.config.models or not any(model.verified for model in self.config.models):
            missing.append({
                "code": "NO_VIDEO_WORKFLOW_CONFIGURED",
                "message": "No verified ComfyUI API-format video workflow is configured.",
            })
        if not available:
            missing.append({
                "code": "NO_LOCAL_VIDEO_MODEL",
                "message": "No configured video model passed ComfyUI capability and workflow validation.",
            })
        return {
            "comfyui": "READY" if api_available else "UNAVAILABLE",
            "api": {key: value for key, value in runtime.items() if key != "object_info"},
            "generation_available": bool(available),
            "models": [self._public(model, available=True) for model in available],
            "model_checks": checks,
            "missing_requirements": _unique(missing),
        }

    def select(self, request: VideoGenerationRequest) -> VideoModelConfig:
        configured = ModelRouter(self.config).select(request)
        report = self.report()
        if report["comfyui"] != "READY":
            raise ModelCapabilityError("COMFYUI_API_UNAVAILABLE: ComfyUI is not available for video generation")
        available = {item["model_id"] for item in report["models"]}
        if configured.model_id not in available:
            check = next((item for item in report["model_checks"] if item["model_id"] == configured.model_id), None)
            reasons = check.get("missing_requirements", []) if isinstance(check, dict) else report["missing_requirements"]
            codes = ", ".join(str(item.get("code")) for item in reasons[:4] if isinstance(item, dict))
            raise ModelCapabilityError(f"NO_LOCAL_VIDEO_MODEL: {codes or 'No verified local video model is available'}")
        return configured

    def _missing_for_model(
        self, model: VideoModelConfig, object_info: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        missing: list[dict[str, str]] = []
        if not model.model_files:
            missing.append({"code": "MODEL_FILE_NOT_FOUND", "message": "No exact model files are configured for this video workflow."})
        if object_info is None:
            return missing
        for class_type in model.required_custom_nodes:
            if class_type not in object_info:
                missing.append({"code": "MISSING_CUSTOM_NODE", "message": f"Required class_type is unavailable: {class_type}"})
        try:
            self.workflows.load_and_validate(model, object_info)
        except ConfigurationError as exc:
            message = str(exc)
            code = "MISSING_CUSTOM_NODE" if "unavailable class_type" in message or "required custom node" in message else "INVALID_WORKFLOW"
            missing.append({"code": code, "message": message})
        return missing

    @staticmethod
    def _public(model: VideoModelConfig, *, available: bool) -> dict[str, Any]:
        return {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "enabled": model.enabled,
            "verified": model.verified,
            "available": available,
            "fps": model.fps,
            "max_duration_seconds": model.max_duration_seconds,
            "aspect_ratios": model.aspect_ratios,
            "supports_image_reference": model.supports_image_reference,
        }


class ModelRouter:
    def __init__(self, config: VideoEngineConfig) -> None:
        self.config = config

    def select(self, request: VideoGenerationRequest) -> VideoModelConfig:
        requested = request.model_id or self.config.default_model
        try:
            model = self.config.model(requested)
        except Exception as exc:
            raise ModelCapabilityError(f"NO_LOCAL_VIDEO_MODEL: video model is not configured: {requested}") from exc
        if not model.enabled:
            raise ModelCapabilityError(f"NO_LOCAL_VIDEO_MODEL: video model is disabled: {requested}")
        if not model.verified:
            raise ModelCapabilityError(f"NO_VIDEO_WORKFLOW_CONFIGURED: {requested} is an unverified template")
        if request.aspect_ratio not in model.aspect_ratios:
            raise ModelCapabilityError(f"{requested} does not support aspect ratio {request.aspect_ratio}")
        if request.video_duration > model.max_duration_seconds:
            raise ModelCapabilityError(f"{requested} supports up to {model.max_duration_seconds:g} seconds per generation")
        if not model.supports_image_reference:
            raise ModelCapabilityError(f"{requested} cannot preserve a character reference image")
        return model

    def public_models(self) -> list[dict[str, object]]:
        return [
            VideoStudioCapabilities._public(item, available=False)
            for item in self.config.models
        ]


def _unique(items: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for item in items:
        key = (item.get("code"), item.get("message"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
