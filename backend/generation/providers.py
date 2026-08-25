"""Generation provider interfaces, adapters, registry, and deterministic mocks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from backend.core.enums import GenerationType, ProviderAvailability
from backend.core.exceptions import ModelCapabilityError, ProviderUnavailableError
from backend.schemas.generation import NormalizedGenerationResult, PromptPackageData


class BaseGenerationProvider(ABC):
    provider_code: str

    @abstractmethod
    def health_check(self) -> ProviderAvailability:
        """Return availability without exposing credentials."""

    @abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        """Describe runtime capabilities."""

    def generate_text(self, request: dict[str, Any]): return self._unsupported(GenerationType.TEXT)
    def generate_image(self, request: dict[str, Any]): return self._unsupported(GenerationType.IMAGE)
    def edit_image(self, request: dict[str, Any]): return self._unsupported(GenerationType.IMAGE_EDIT)
    def generate_video(self, request: dict[str, Any]): return self._unsupported(GenerationType.VIDEO)
    def generate_audio(self, request: dict[str, Any]): return self._unsupported(GenerationType.AUDIO)
    def submit_job(self, request: dict[str, Any]): return self.generate(request)
    def get_job_status(self, external_job_id: str) -> str: return "completed"
    def fetch_result(self, external_job_id: str): raise ModelCapabilityError("Async fetch is unsupported")
    def cancel_job(self, external_job_id: str) -> bool: return False

    def generate(self, request: dict[str, Any]):
        generation_type = GenerationType(request["generation_type"])
        if generation_type in {GenerationType.TEXT, GenerationType.COPY, GenerationType.SCRIPT, GenerationType.STORYBOARD, GenerationType.CAPTIONS, GenerationType.TRANSCRIPT, GenerationType.AUDIO_DESCRIPTION_DRAFT, GenerationType.MUSIC_BRIEF}:
            return self.generate_text(request)
        if generation_type in {GenerationType.IMAGE, GenerationType.IMAGE_VARIATION}:
            return self.generate_image(request)
        if generation_type is GenerationType.IMAGE_EDIT:
            return self.edit_image(request)
        if generation_type in {GenerationType.VIDEO, GenerationType.VIDEO_SHOT, GenerationType.VIDEO_SEQUENCE}:
            return self.generate_video(request)
        if generation_type in {GenerationType.AUDIO, GenerationType.VOICE, GenerationType.SFX}:
            return self.generate_audio(request)
        if generation_type is GenerationType.MULTIMODAL_PACKAGE:
            return self.generate_text(request)
        return self._unsupported(generation_type)

    def normalize_response(self, response: Any, *, model_id: str, model_version: str) -> NormalizedGenerationResult:
        if isinstance(response, NormalizedGenerationResult): return response
        raise ProviderUnavailableError("Provider returned an unsupported response contract")

    @staticmethod
    def _unsupported(operation):
        raise ModelCapabilityError(f"Unsupported generation operation: {operation}")


class ProviderPromptAdapter:
    """Translate neutral packages without leaking provider details into core."""

    def translate(self, package: PromptPackageData, model_capabilities: dict[str, Any]) -> dict[str, Any]:
        references = []
        for reference in package.reference_assets:
            translated = reference.model_dump(mode="json")
            translated["provider_parameters"] = {
                key: value for key, value in {
                    "identity_priority": reference.identity_priority,
                    "composition_priority": reference.composition_priority,
                    "pose_priority": reference.pose_priority,
                    "product_priority": reference.product_priority,
                }.items() if value is not None
            }
            references.append(translated)
        return {
            "generation_type": package.generation_type.value,
            "structured_prompt": package.model_dump(mode="json", exclude={"reference_assets"}),
            "references": references,
            "output_specification": package.output_specification.model_dump(mode="json", exclude_none=True),
        }


class MockGenerationProvider(BaseGenerationProvider):
    """Deterministic no-cost provider used by automated tests and local previews."""

    def __init__(self, provider_code: str, *, fail_times: int = 0, output_metadata: dict[str, Any] | None = None) -> None:
        self.provider_code = provider_code
        self.fail_times = fail_times
        self.output_metadata = output_metadata or {}
        self.call_count = 0
        self.cancelled: set[str] = set()

    def health_check(self):
        return ProviderAvailability.AVAILABLE

    def get_capabilities(self):
        return {"mock": True, "no_external_calls": True}

    def _result(self, request, modality):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise ProviderUnavailableError("Synthetic provider failure")
        canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)
        token = sha256(canonical.encode("utf-8")).hexdigest()[:24]
        generation_type = GenerationType(request["generation_type"])
        structured = request.get("structured_prompt", {})
        character = structured.get("character") or {}
        product = structured.get("product") or {}
        brand = structured.get("brand") or {}
        hair = character.get("hair") or {}
        derived = {
            "character_hair_color": hair.get("color") if isinstance(hair, dict) else None,
            "product_label": product.get("label") or product.get("name"),
            "background_color": (brand.get("palette") or [None])[0],
        }
        output_spec = request.get("output_specification") or {}
        if output_spec.get("resolution") and "x" in output_spec["resolution"]:
            width, height = output_spec["resolution"].lower().split("x", 1)
            derived.update({"width": int(width), "height": int(height)})
        for key in ("width", "height", "aspect_ratio", "duration_seconds", "color_profile", "sample_rate", "frame_rate"):
            if output_spec.get(key) is not None:
                derived[key] = output_spec[key]
        metadata = {"mock": True, "token": token, **{k: v for k, v in derived.items() if v is not None}, **self.output_metadata, **request.get("mock_output_metadata", {})}
        if modality == "text":
            contract = structured
            approved_claims = ((contract.get("product") or {}).get("approved_claims") or [])
            text = {
                "copy_uid": f"COPY_{token}", "copy_type": generation_type.value,
                "headline": "Synthetic headline", "hook": "Synthetic hook", "body": "Synthetic body",
                "cta": "Learn more", "claims": approved_claims, "keywords": [],
                "evidence_links": [], "confidence": 1.0, "version": 1,
            }
            if "claims" in metadata:
                text["claims"] = list(metadata["claims"])
            if generation_type is GenerationType.SCRIPT:
                text = {
                    "script_uid": f"SCRIPT_{token}", "duration_target": contract.get("output_specification", {}).get("duration_seconds"),
                    "segments": [{"segment_id": "SEG_001", "role": "hook", "start_target": 0.0, "duration_target": 3.0,
                                  "spoken_copy": "Synthetic hook", "on_screen_text": None, "visual_action": "Establish subject",
                                  "product_action": None, "audio": {}, "transition": None, "cta": None, "accessibility_note": None}],
                }
            if generation_type is GenerationType.STORYBOARD:
                text = {"shots": contract.get("scene", {}).get("shots") or [{"shot_id": "SHOT_001", "purpose": "establish", "duration": 3.0}]}
                metadata["storyboard"] = text["shots"]
            if generation_type is GenerationType.CAPTIONS:
                text = {"format": "structured_json", "timing_source": "actual_audio", "cues": [{"start": 0.0, "end": 2.0, "text": "Synthetic caption"}]}
            if generation_type is GenerationType.TRANSCRIPT:
                text = {"media_version_required": True, "segments": [{"start": 0.0, "end": 2.0, "text": "Synthetic transcript"}]}
            if generation_type is GenerationType.AUDIO_DESCRIPTION_DRAFT:
                text = {"draft": True, "essential_visual_information": [], "available_pauses": [], "description_lines": []}
            return NormalizedGenerationResult(
                provider=self.provider_code, model_id=request["model_id"], model_version=request["model_version"],
                external_job_id=f"MOCK_{uuid4().hex}", status="completed", text_outputs=[text], metadata=metadata,
                cost_metadata={"provider_cost": 0.0, "currency": "USD", "estimated": False},
                timing={"generation_seconds": 0.0},
            )
        mime = {"image": "image/png", "video": "video/mp4", "audio": "audio/wav"}[modality]
        extension = {"image": "png", "video": "mp4", "audio": "wav"}[modality]
        content = f"EMY_MOCK_{modality.upper()}_{token}".encode("utf-8")
        asset = {"content": content, "mime_type": mime, "extension": extension, "metadata": metadata}
        return NormalizedGenerationResult(
            provider=self.provider_code, model_id=request["model_id"], model_version=request["model_version"],
            external_job_id=f"MOCK_{uuid4().hex}", status="completed", media_assets=[asset], metadata=metadata,
            cost_metadata={"provider_cost": 0.0, "currency": "USD", "estimated": False},
            timing={"generation_seconds": 0.0},
        )

    def generate_text(self, request): return self._result(request, "text")
    def generate_image(self, request): return self._result(request, "image")
    def edit_image(self, request): return self._result(request, "image")
    def generate_video(self, request): return self._result(request, "video")
    def generate_audio(self, request): return self._result(request, "audio")
    def cancel_job(self, external_job_id): self.cancelled.add(external_job_id); return True


class ProviderRegistry:
    def __init__(self, *, health_ttl_seconds: int = 30) -> None:
        self._providers: dict[str, BaseGenerationProvider] = {}
        self._health_cache: dict[str, tuple[datetime, ProviderAvailability]] = {}
        self.health_ttl = timedelta(seconds=health_ttl_seconds)

    def register(self, provider: BaseGenerationProvider) -> None:
        self._providers[provider.provider_code] = provider

    def get(self, provider_code: str) -> BaseGenerationProvider:
        provider = self._providers.get(provider_code)
        if provider is None:
            raise ProviderUnavailableError(f"Provider is not registered: {provider_code}")
        return provider

    def health(self, provider_code: str, *, force: bool = False) -> ProviderAvailability:
        now = datetime.now(UTC)
        cached = self._health_cache.get(provider_code)
        if cached and not force and now - cached[0] < self.health_ttl:
            return cached[1]
        status = self.get(provider_code).health_check()
        self._health_cache[provider_code] = (now, status)
        return status

    def list(self):
        return list(self._providers.values())
