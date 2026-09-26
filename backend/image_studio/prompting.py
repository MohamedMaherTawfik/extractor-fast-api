"""Prompt and preset construction without model-specific assumptions."""

from __future__ import annotations

from copy import deepcopy

from backend.image_studio.schemas import ImageStudioSettings


NEGATIVE_PROMPT = (
    "face distortion, identity drift, different person, different product, product deformation, "
    "packaging deformation, wrong logo, wrong label, extra fingers, duplicate hands, deformed hands, "
    "bad anatomy, extra limbs, plastic skin, over-smoothed skin, unnatural eyes, asymmetrical face, "
    "text artifacts, watermark, low resolution, blur, duplicate product, floating product, cropped product, "
    "incorrect proportions"
)

CAMERA_MAPPING = {
    "Front": "frontal composition at eye level",
    "3/4 Front": "three-quarter front composition at eye level",
    "45 Degree": "45 degree three-quarter view",
    "Side Profile": "side-profile composition",
    "3/4 Back": "three-quarter back view while keeping the product visible",
    "Low Angle": "camera below eye level",
    "High Angle": "camera above the subject",
    "Top Down": "top-down composition",
    "Over The Shoulder": "over-the-shoulder composition with the product clearly visible",
    "Close-Up": "tight close-up framing",
    "Extreme Close-Up": "extreme close-up framing with essential product details in frame",
}

PRESETS: dict[str, dict[str, str | int]] = {
    "PREMIUM_PRODUCT_HERO": {"camera_angle": "45 Degree", "shot_type": "Product Hero", "pose": "Presenting Product", "background": "Luxury Studio", "lighting": "Product Commercial", "visual_style": "Premium Commercial", "aspect_ratio": "4:5", "number_of_images": 1},
    "BEAUTY_COMMERCIAL": {"camera_angle": "45 Degree", "shot_type": "Medium Close-Up", "pose": "Product Near Face", "background": "Beauty Studio", "lighting": "Beauty Lighting", "visual_style": "Luxury Beauty", "aspect_ratio": "4:5", "number_of_images": 1},
    "LUXURY_CAMPAIGN": {"camera_angle": "3/4 Front", "shot_type": "3/4 Body", "pose": "Holding Product", "background": "Luxury Studio", "lighting": "Cinematic", "visual_style": "Premium Commercial", "aspect_ratio": "4:5", "number_of_images": 2},
    "SOCIAL_MEDIA_AD": {"camera_angle": "Front", "shot_type": "Medium Shot", "pose": "Presenting Product", "background": "Commercial", "lighting": "High Key", "visual_style": "Social Media Ad", "aspect_ratio": "9:16", "number_of_images": 2},
    "E_COMMERCE": {"camera_angle": "Front", "shot_type": "Product Hero", "pose": "Product On Table", "background": "Pure Studio", "lighting": "Product Commercial", "visual_style": "E-commerce", "aspect_ratio": "1:1", "number_of_images": 1},
    "CREATOR_UGC": {"camera_angle": "Front", "shot_type": "Medium Shot", "pose": "Using Product", "background": "Home", "lighting": "Soft Studio", "visual_style": "UGC", "aspect_ratio": "9:16", "number_of_images": 2},
    "PRODUCT_CLOSE_UP": {"camera_angle": "Close-Up Angle", "shot_type": "Product Detail", "pose": "Product In Hand", "background": "Minimal", "lighting": "Product Commercial", "visual_style": "Photorealistic", "aspect_ratio": "1:1", "number_of_images": 1},
    "LIFESTYLE_PRODUCT": {"camera_angle": "3/4 Front", "shot_type": "3/4 Body", "pose": "Using Product", "background": "Lifestyle", "lighting": "Golden Hour", "visual_style": "Editorial", "aspect_ratio": "4:5", "number_of_images": 2},
}


def preset_catalog() -> list[dict[str, object]]:
    return [{"preset_id": key, "name": key.replace("_", " ").title(), "settings": deepcopy(value)} for key, value in PRESETS.items()]


def apply_preset(settings: ImageStudioSettings) -> ImageStudioSettings:
    if not settings.preset_id or settings.preset_id not in PRESETS:
        return settings
    defaults = ImageStudioSettings().model_dump()
    values = settings.model_dump()
    for field, value in PRESETS[settings.preset_id].items():
        if values.get(field) == defaults.get(field):
            values[field] = value
    return ImageStudioSettings.model_validate(values)


def _choice(value: str, custom: str | None) -> str:
    return custom if value == "Custom" and custom else value


def build_prompt(settings: ImageStudioSettings) -> tuple[str, str]:
    action = _choice(settings.pose, settings.custom_pose)
    background = _choice(settings.background, settings.custom_background)
    lighting = _choice(settings.lighting, settings.custom_lighting)
    style = _choice(settings.visual_style, settings.custom_visual_style)
    creative = f" Creative direction: {settings.creative_direction}." if settings.creative_direction else ""
    prompt = (
        "Create a photorealistic premium commercial advertising image. "
        "Character: preserve identity from the supplied character reference, including face identity, "
        "facial features, skin tone, hair, hairstyle, body proportions, and general appearance. "
        "Product: preserve the exact appearance from the supplied product reference, including product shape, "
        "packaging, colors, proportions, label, logo, visible branding, container geometry, and product details. "
        f"Camera: {CAMERA_MAPPING.get(settings.camera_angle, settings.camera_angle)}. "
        f"Shot: {settings.shot_type.lower()}. Action: {action.lower()}. "
        f"Background: {background.lower()}. Lighting: {lighting.lower()}. Style: {style.lower()}. "
        f"Compose for a {settings.aspect_ratio} aspect ratio.{creative} "
        "Do not invent product details that are not visible in the reference."
    )
    return prompt, NEGATIVE_PROMPT
