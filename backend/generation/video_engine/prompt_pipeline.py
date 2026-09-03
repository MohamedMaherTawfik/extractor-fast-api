"""Master-prompt recipes and character-aware prompt compilation."""

from __future__ import annotations

import json

from backend.core.exceptions import PromptConflictError
from backend.generation.video_engine.config import VideoEngineConfig
from backend.generation.video_engine.schemas import CharacterProfile, PromptPackage, VideoGenerationRequest


class PromptPipeline:
    def __init__(self, config: VideoEngineConfig) -> None:
        self.config = config

    def build(self, request: VideoGenerationRequest, character: CharacterProfile) -> PromptPackage:
        recipe = self.config.recipe(request.recipe_id)
        master = request.master_prompt.strip() if request.master_prompt else recipe.master_prompt
        if not master:
            raise PromptConflictError("A master prompt or a configured recipe master prompt is required")
        identity = {
            "character_id": character.character_id,
            "character_version": character.version,
            "reference_checksum": character.reference_checksum,
            "identity_data": character.identity_data,
            "style_profile": character.style_profile,
            "recurring_attributes": character.recurring_attributes,
            "preserve": ["face identity", "hairstyle", "body proportions", "visual style"],
        }
        identity_text = json.dumps(identity, ensure_ascii=False, sort_keys=True)
        positive = "\n".join([
            master,
            f"Creative direction: {request.creative_idea}.",
            f"Character identity lock (must remain unchanged in every frame): {identity_text}.",
            f"Camera: {request.camera_motion}; recipe camera style: {recipe.camera_style}.",
            f"Lighting: {recipe.lighting}. Color language: {recipe.colors}.",
            f"Environment: {recipe.environment}. Realism: {recipe.realism_level}.",
            f"Motion: {recipe.motion_style}. Requested visual style: {request.style}.",
            f"Output: {request.video_duration:g} seconds, {request.aspect_ratio} aspect ratio, temporal continuity, stable anatomy and consistent wardrobe.",
        ])
        negatives = [
            *recipe.negative_prompt, *character.negative_constraints,
            "identity drift", "face morphing", "hairstyle changes", "body proportion changes",
            "flicker", "frame-to-frame inconsistency", "duplicate limbs", "deformed hands",
            "text artifacts", "watermark", "low resolution",
        ]
        negative = ", ".join(dict.fromkeys(item.strip() for item in negatives if item.strip()))
        script = {
            "title": request.creative_idea[:120],
            "duration_seconds": request.video_duration,
            "beats": [
                {"position": "opening", "direction": "Establish the character and product context", "duration_ratio": 0.25},
                {"position": "middle", "direction": request.creative_idea, "duration_ratio": 0.55},
                {"position": "close", "direction": "Resolve with a clean hero frame", "duration_ratio": 0.20},
            ],
            "camera_motion": request.camera_motion,
        }
        return PromptPackage(
            recipe_id=recipe.recipe_id, master_prompt=master, positive_prompt=positive,
            negative_prompt=negative, script=script, identity_constraints=identity,
        )
