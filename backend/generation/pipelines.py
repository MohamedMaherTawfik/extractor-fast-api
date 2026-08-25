"""Focused modality planning, provider execution, assembly, and retry helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
import json
from typing import Any

from backend.core.enums import GenerationRetryType, GenerationType
from backend.core.exceptions import ReferenceSafetyError
from backend.schemas.generation import NormalizedGenerationResult, StoryboardShotData


class CopyGenerationService:
    def generate(self, provider, adapter_request):
        return provider.generate_text(adapter_request)


class ImageGenerationService:
    def generate(self, provider, adapter_request):
        return provider.edit_image(adapter_request) if adapter_request["generation_type"] == GenerationType.IMAGE_EDIT.value else provider.generate_image(adapter_request)


class StoryboardGenerationService:
    def plan(self, package) -> list[StoryboardShotData]:
        explicit = package.scene.get("shots") or []
        if explicit:
            return [StoryboardShotData.model_validate(item) for item in explicit]
        segments = package.scene.get("segments") or package.scene.get("segment_sequence") or []
        if not segments:
            return [StoryboardShotData(shot_id="SHOT_001", purpose="establish", duration=3.0)]
        shots = []
        for index, segment in enumerate(segments, start=1):
            value = segment if isinstance(segment, dict) else {"purpose": str(segment)}
            shots.append(StoryboardShotData(
                shot_id=f"SHOT_{index:03d}", segment_id=str(value.get("segment_id") or index),
                purpose=str(value.get("purpose") or value.get("role") or "story beat"),
                duration=float(value.get("duration") or value.get("duration_target") or 3.0),
                dialogue=value.get("spoken_copy"), background=value.get("background"),
                lighting=value.get("lighting"), transition=value.get("transition"),
                dependency={
                    "previous_shot": f"SHOT_{index - 1:03d}" if index > 1 else None,
                    "character_state": value.get("character_state"), "wardrobe_state": value.get("wardrobe_state"),
                    "product_state": value.get("product_state"), "camera_direction": value.get("screen_direction"),
                    "background_state": value.get("background"), "lighting_state": value.get("lighting"),
                },
            ))
        return shots

    def generate(self, provider, adapter_request):
        return provider.generate_text(adapter_request)


class VideoGenerationService:
    def __init__(self, storyboard: StoryboardGenerationService | None = None) -> None:
        self.storyboard = storyboard or StoryboardGenerationService()

    def generate(self, provider, adapter_request, package):
        generation_type = GenerationType(adapter_request["generation_type"])
        if generation_type is GenerationType.VIDEO_SHOT:
            return provider.generate_video(adapter_request)
        shots = self.storyboard.plan(package)
        media_assets = []
        shot_states = []
        warnings = []
        total_cost = 0.0
        for shot in shots:
            request = deepcopy(adapter_request)
            request["generation_type"] = GenerationType.VIDEO_SHOT.value
            request["structured_prompt"]["scene"] = {"shot": shot.model_dump(mode="json")}
            result = provider.generate_video(request)
            for asset in result.media_assets:
                asset.setdefault("metadata", {}).update({"shot_id": shot.shot_id, "duration_seconds": shot.duration})
                media_assets.append(asset)
            shot_states.append({
                "shot_id": shot.shot_id,
                "wardrobe": (package.character or {}).get("wardrobe"),
                "hair": (package.character or {}).get("hair"),
                "product_state": shot.dependency.get("product_state"),
                "background_state": shot.background,
                "lighting": shot.lighting,
                "screen_direction": shot.dependency.get("camera_direction"),
            })
            total_cost += float(result.cost_metadata.get("provider_cost", 0.0))
        return NormalizedGenerationResult(
            provider=provider.provider_code, model_id=adapter_request["model_id"], model_version=adapter_request["model_version"],
            status="completed", media_assets=media_assets,
            metadata={"storyboard": [item.model_dump(mode="json") for item in shots], "shot_states": shot_states},
            cost_metadata={"provider_cost": total_cost, "currency": "USD", "estimated": False}, warnings=warnings,
        )


class AudioGenerationService:
    def generate(self, provider, adapter_request, package):
        character = package.character or {}
        voice = character.get("voice") or character.get("voice_profile") or {}
        if adapter_request["generation_type"] == GenerationType.VOICE.value:
            rights = str(voice.get("rights_status") or voice.get("consent_status") or "UNKNOWN").upper()
            if rights != "CLEARED":
                raise ReferenceSafetyError("Voice generation requires explicit cleared rights and consent")
        return provider.generate_audio(adapter_request)

    @staticmethod
    def audio_mix_plan(dialogue=None, music=None, sfx=None, ambience=None, foley=None, audio_description=None, loudness_profile=None):
        return {
            "dialogue_stem": dialogue, "music_stem": music, "sfx_stem": sfx or [],
            "ambience": ambience, "foley": foley or [], "audio_description": audio_description,
            "ducking_instructions": [{"under": "dialogue", "target": "music"}],
            "loudness_profile": loudness_profile or "contract_defined", "true_peak_profile": "contract_defined",
        }


class VideoAssemblyService:
    """Plan safe ordered assembly; an FFmpeg adapter can replace this boundary."""

    def build_plan(self, shots, *, transitions=None, audio_tracks=None, caption_tracks=None):
        return {
            "ordered_shots": [{"asset_uid": item["asset_uid"], "duration": item.get("duration"), "index": index} for index, item in enumerate(shots)],
            "transitions": transitions or [], "audio_tracks": audio_tracks or [],
            "caption_tracks": caption_tracks or [], "assembly_backend": "manifest_only",
            "ffmpeg_available": False, "shell_execution": False,
        }


class AccessibilityGenerationService:
    @staticmethod
    def package(contract, *, final_asset_uid: str, actual_audio_timing=None):
        requirements = contract.get("accessibility_requirements") or []
        text = " ".join(str(item).lower() for item in requirements)
        return {
            "final_asset_uid": final_asset_uid,
            "caption_job_required": "caption" in text,
            "caption_timing_source": "actual_audio" if actual_audio_timing else "pending_final_audio",
            "transcript_required": "transcript" in text,
            "audio_description_plan_required": "audio description" in text or "audio_description" in text,
            "alt_text_required": "alt text" in text or "alt_text" in text,
            "reduced_motion_variant_required": "reduced motion" in text,
            "sign_language_task_required": "sign language" in text,
            "final_human_approval_required": "audio description" in text or "sign language" in text,
        }


class ProvenanceAdapter(ABC):
    @abstractmethod
    def attach(self, asset_version, provenance: dict[str, Any]) -> str:
        """Return external provenance status/reference."""


class DeferredC2PAProvenanceAdapter(ProvenanceAdapter):
    def attach(self, asset_version, provenance):
        return "not_available"


class GenerationRetryService:
    def plan(self, *, attempt: int, max_attempts: int, primary, fallbacks, error_code: str):
        if attempt >= max_attempts:
            return None
        if fallbacks:
            return {
                "retry_type": GenerationRetryType.FALLBACK_MODEL,
                "model": fallbacks.pop(0), "reason": error_code,
                "changes_applied": {"provider_fallback": True},
            }
        return {
            "retry_type": GenerationRetryType.SAME_MODEL_RETRY,
            "model": primary, "reason": error_code, "changes_applied": {},
        }


class GenerationQueue(ABC):
    @abstractmethod
    def submit(self, job_uid: str) -> str: ...
    @abstractmethod
    def cancel(self, job_uid: str) -> bool: ...


class LocalGenerationQueue(GenerationQueue):
    """Non-blocking boundary marker for a future durable worker."""
    def __init__(self): self.queued: list[str] = []
    def submit(self, job_uid): self.queued.append(job_uid); return job_uid
    def cancel(self, job_uid):
        if job_uid in self.queued: self.queued.remove(job_uid); return True
        return False
