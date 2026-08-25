"""Capability registry and policy-based model selection."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.core.enums import ProviderAvailability, ProviderLocality, ProviderPreference
from backend.core.exceptions import ModelCapabilityError
from backend.generation.providers import MockGenerationProvider, ProviderRegistry
from backend.repositories.generation_repository import GenerationRepository
from backend.schemas.generation import (
    ModelCapabilities, ModelProfileCreate, ModelProfileResponse, ProviderProfileCreate,
    RequiredCapabilities,
)
from backend.services.generation_config import load_generation_config


class ModelCapabilityRegistry:
    def __init__(self, session: Session, providers: ProviderRegistry | None = None) -> None:
        self.repository = GenerationRepository(session)
        self.config = load_generation_config()
        self.providers = providers or ProviderRegistry(health_ttl_seconds=self.config.health_cache_seconds)
        self._ensure_configured_profiles()

    def _ensure_configured_profiles(self):
        for payload in self.config.providers:
            profile = ProviderProfileCreate.model_validate(payload)
            self.repository.upsert_provider(**profile.model_dump())
            if profile.provider_code not in {item.provider_code for item in self.providers.list()}:
                self.providers.register(MockGenerationProvider(profile.provider_code))
        for payload in self.config.models:
            profile = ModelProfileCreate.model_validate(payload)
            provider = self.repository.get_provider(profile.provider_code)
            if provider is None: continue
            self.repository.upsert_model(
                provider_id=provider.id, locality=provider.locality,
                **profile.model_dump(exclude={"capabilities"}),
                capabilities=profile.capabilities.model_dump(mode="json"),
            )

    def list_models(self):
        return [ModelProfileResponse.model_validate(item) for item in self.repository.list_models()]

    def matching(self, required: RequiredCapabilities):
        matches = []
        for model in self.repository.list_models():
            capabilities = ModelCapabilities.model_validate(model.capabilities)
            if not model.enabled or model.availability is not ProviderAvailability.AVAILABLE: continue
            if required.generation_type not in capabilities.outputs: continue
            if required.needs_seed and not capabilities.supports_seed: continue
            if required.needs_references and not capabilities.supports_reference_images: continue
            if required.needs_mask_editing and not capabilities.supports_mask_editing: continue
            if required.needs_image_to_video and not capabilities.supports_image_to_video: continue
            if required.needs_audio_conditioning and not capabilities.supports_audio_conditioning: continue
            if required.aspect_ratio and capabilities.supported_aspect_ratios and required.aspect_ratio not in capabilities.supported_aspect_ratios: continue
            if required.resolution and capabilities.supported_resolutions and required.resolution not in capabilities.supported_resolutions: continue
            if required.duration_seconds and capabilities.max_output_duration and required.duration_seconds > capabilities.max_output_duration: continue
            if self.providers.health(model.provider_code) is ProviderAvailability.UNAVAILABLE: continue
            matches.append(model)
        return matches


@dataclass(frozen=True)
class ModelSelection:
    primary: object
    fallbacks: list[object]


class ModelSelectorService:
    def __init__(self, registry: ModelCapabilityRegistry) -> None:
        self.registry = registry

    def select(self, required: RequiredCapabilities, *, preference: ProviderPreference | None = None, requested_model: str | None = None) -> ModelSelection:
        preference = preference or self.registry.config.provider_preference
        candidates = self.registry.matching(required)
        if requested_model:
            candidates = [item for item in candidates if item.model_id == requested_model]
        if preference is ProviderPreference.FORCE_LOCAL:
            candidates = [item for item in candidates if item.locality is ProviderLocality.LOCAL]
        elif preference is ProviderPreference.FORCE_REMOTE:
            candidates = [item for item in candidates if item.locality is ProviderLocality.REMOTE]
        if not candidates:
            raise ModelCapabilityError(f"No enabled model satisfies {required.generation_type.value}")
        def score(item):
            locality = 0.0
            if preference is ProviderPreference.LOCAL_FIRST: locality = 2.0 if item.locality is ProviderLocality.LOCAL else 0.0
            elif preference is ProviderPreference.REMOTE_FIRST: locality = 2.0 if item.locality is ProviderLocality.REMOTE else 0.0
            elif preference is ProviderPreference.BALANCED: locality = 0.5
            return (locality + item.quality_score + item.privacy_score + item.cost_score + item.latency_score, item.provider_code, item.model_id)
        ordered = sorted(candidates, key=score, reverse=True)
        return ModelSelection(primary=ordered[0], fallbacks=ordered[1:])
