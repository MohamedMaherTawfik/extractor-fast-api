"""Config-driven routing across local open video model workflows."""

from backend.core.exceptions import ModelCapabilityError
from backend.generation.video_engine.config import VideoEngineConfig, VideoModelConfig
from backend.generation.video_engine.schemas import VideoGenerationRequest


class ModelRouter:
    def __init__(self, config: VideoEngineConfig) -> None:
        self.config = config

    def select(self, request: VideoGenerationRequest) -> VideoModelConfig:
        requested = request.model_id or self.config.default_model
        try:
            model = self.config.model(requested)
        except Exception as exc:
            raise ModelCapabilityError(f"Video model is not configured: {requested}") from exc
        if not model.enabled:
            raise ModelCapabilityError(f"Video model is disabled: {requested}")
        if request.aspect_ratio not in model.aspect_ratios:
            raise ModelCapabilityError(f"{requested} does not support aspect ratio {request.aspect_ratio}")
        if request.video_duration > model.max_duration_seconds:
            raise ModelCapabilityError(
                f"{requested} supports up to {model.max_duration_seconds:g} seconds per generation"
            )
        if not model.supports_image_reference:
            raise ModelCapabilityError(f"{requested} cannot preserve a character reference image")
        return model

    def public_models(self) -> list[dict[str, object]]:
        return [
            {
                "model_id": item.model_id, "display_name": item.display_name,
                "enabled": item.enabled, "fps": item.fps,
                "max_duration_seconds": item.max_duration_seconds,
                "aspect_ratios": item.aspect_ratios,
                "supports_image_reference": item.supports_image_reference,
            }
            for item in self.config.models
        ]
