"""Validated contracts for product-image generation jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator


CameraAngle = Literal[
    "Front", "Straight On", "3/4 Front", "30 Degree",
    "45 Degree", "60 Degree", "Side Profile", "3/4 Back",
    "Back", "Low Angle", "Very Low Angle", "Eye Level",
    "High Angle", "Very High Angle", "Top Down", "Bird's Eye",
    "Worm's Eye", "Over The Shoulder", "POV", "First Person",
    "Dutch Angle", "Tilted Angle", "Product POV", "Product Perspective",
    "Close-Up Angle", "Extreme Close-Up Angle", "Macro Angle", "Custom"
]


ShotType = Literal[
    "Extreme Wide Shot", "Wide Shot", "Full Shot", "Full Body",
    "3/4 Body", "American Shot", "Cowboy Shot", "Knee Shot",
    "Medium Long Shot", "Medium Shot", "Waist Shot", "Medium Close-Up",
    "Bust Shot", "Head Shot", "Close-Up", "Extreme Close-Up",
    "Macro", "Product Hero", "Product Detail", "Product Macro",
    "Product Close-Up", "Product Wide Shot", "Product Catalog", "Product Advertising",
    "Environmental Product Shot", "Character + Product", "Character Portrait", "Lifestyle Shot",
    "Editorial Shot", "Commercial Shot", "Custom"
]


Pose = Literal[
    "Standing", "Walking", "Running", "Sitting",
    "Kneeling", "Squatting", "Crouching", "Leaning",
    "Lying Down", "Turning", "Looking Back", "Looking Forward",
    "Looking Away", "Looking At Camera", "Looking At Product", "Looking Down",
    "Looking Up", "Holding Product", "Holding Product With One Hand", "Holding Product With Both Hands",
    "Presenting Product", "Showing Product", "Using Product", "Demonstrating Product",
    "Applying Product", "Wearing Product", "Product Near Face", "Product Near Chest",
    "Product Near Shoulder", "Product Near Waist", "Product In Hand", "Product On Table",
    "Product On Counter", "Product On Shelf", "Walking With Product", "Sitting With Product",
    "Pointing At Product", "Touching Product", "Reaching For Product", "Opening Product",
    "Closing Product", "Unboxing Product", "Comparing Products", "Gesturing",
    "Arms Crossed", "Hands On Waist", "Hands At Side", "One Hand In Pocket",
    "Both Hands In Pockets", "Hand Near Face", "Hand In Hair", "Custom"
]


Background = Literal[
    "Pure Studio", "White Studio", "Black Studio", "Gray Studio",
    "Beige Studio", "Luxury Studio", "Beauty Studio", "Fashion Studio",
    "Commercial Studio", "Product Studio", "Minimal", "Clean Minimal",
    "Modern Studio", "Editorial Studio", "Luxury Interior", "Modern Interior",
    "Classic Interior", "Minimal Interior", "Home", "Living Room",
    "Bedroom", "Bathroom", "Kitchen", "Dining Room",
    "Office", "Modern Office", "Conference Room", "Hotel",
    "Luxury Hotel", "Restaurant", "Cafe", "Coffee Shop",
    "Retail Store", "Luxury Store", "Showroom", "Mall",
    "Gym", "Spa", "Salon", "Clinic",
    "Laboratory", "Warehouse", "Factory", "Industrial",
    "Commercial", "Street", "Urban", "Downtown",
    "City", "Architecture", "Beach", "Poolside",
    "Garden", "Forest", "Mountain", "Desert",
    "Countryside", "Nature", "Resort", "Airport",
    "Car Interior", "Vehicle", "Outdoor", "Indoor",
    "Lifestyle", "Custom"
]


Lighting = Literal[
    "Soft Studio", "Beauty Lighting", "Cinematic", "High Key",
    "Low Key", "Golden Hour", "Blue Hour", "Daylight",
    "Natural Light", "Window Light", "Softbox", "Large Softbox",
    "Small Softbox", "Beauty Dish", "Ring Light", "Strip Light",
    "Umbrella Lighting", "Butterfly Lighting", "Rembrandt Lighting", "Loop Lighting",
    "Split Lighting", "Rim Light", "Edge Light", "Backlight",
    "Side Light", "Front Light", "Top Light", "Bottom Light",
    "Hard Light", "Soft Light", "Diffused Light", "Directional Light",
    "Dramatic Light", "Product Commercial", "Luxury Commercial", "Fashion Lighting",
    "Editorial Lighting", "Neon Lighting", "Color Gel Lighting", "Practical Lighting",
    "Ambient Lighting", "Volumetric Lighting", "Natural Window Lighting", "Sunlight",
    "Overcast Light", "Studio Flash", "Mixed Lighting", "Custom"
]


VisualStyle = Literal[
    "Premium Commercial", "Luxury Beauty", "Luxury Fashion", "Luxury Commercial",
    "Editorial", "Fashion Editorial", "Photorealistic", "Hyperrealistic",
    "Ultra Photorealistic", "E-commerce", "Product Photography", "Product Advertising",
    "Social Media Ad", "Instagram Ad", "TikTok Ad", "UGC",
    "Natural UGC", "Cinematic", "Cinematic Photography", "Film Look",
    "Documentary", "Magazine", "Beauty Campaign", "Fashion Campaign",
    "Lifestyle Advertising", "Lifestyle Photography", "Minimal Commercial", "Clean Commercial",
    "High-End Advertising", "Corporate", "Professional", "Studio Photography",
    "Portrait Photography", "Beauty Photography", "Product Photography", "Macro Photography",
    "Street Photography", "Natural Photography", "Realistic Advertising", "Luxury Editorial",
    "Modern Advertising", "Classic Advertising", "Contemporary", "Artistic",
    "Conceptual", "Futuristic", "Minimalist", "Premium Lifestyle",
    "Custom"
]


AspectRatio = Literal[
    "1:1", "4:5", "3:4", "2:3",
    "9:16", "16:9", "4:3", "3:2",
    "21:9", "9:21", "5:4", "4:1",
    "1:4", "2:1", "1:2", "Custom"
]


class ImageStudioSettings(BaseModel):
    preset_id: str | None = Field(default=None, max_length=100)

    camera_angle: CameraAngle = "45 Degree"
    shot_type: ShotType = "Medium Close-Up"

    pose: Pose = "Holding Product"
    custom_pose: str | None = Field(default=None, max_length=2000)

    background: Background = "Luxury Studio"
    custom_background: str | None = Field(default=None, max_length=2000)

    lighting: Lighting = "Soft Studio"
    custom_lighting: str | None = Field(default=None, max_length=2000)

    visual_style: VisualStyle = "Premium Commercial"
    custom_visual_style: str | None = Field(default=None, max_length=2000)

    aspect_ratio: AspectRatio = "4:5"

    number_of_images: Literal[1, 2, 4, 8] = 1

    creative_direction: str = Field(default="", max_length=4000)

    model_id: str | None = Field(default=None, max_length=150)

    seed: int | None = Field(
        default=None,
        ge=0,
        le=2_147_483_647
    )

    @field_validator(
        "custom_pose",
        "custom_background",
        "custom_lighting",
        "custom_visual_style",
        "creative_direction",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class ImageReference(BaseModel):
    filename: str
    mime_type: str
    file_size: int
    width: int
    height: int
    relative_path: str
    checksum: str


class ImageStudioJob(BaseModel):
    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    stage: str

    settings: dict[str, Any]

    character_image: ImageReference
    product_image: ImageReference

    prompt: str
    negative_prompt: str

    workflow: dict[str, Any] | None = None
    model: dict[str, Any] | None = None

    seed: int | None = None
    execute: bool = True

    comfyui_prompt_ids: list[str] = Field(default_factory=list)

    output_images: list[dict[str, Any]] = Field(default_factory=list)

    error: dict[str, Any] | None = None

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InjectionTarget(BaseModel):
    node_id: str
    input: str


class ImageModelConfig(BaseModel):
    model_id: str = Field(min_length=1, max_length=150)
    display_name: str = Field(min_length=1, max_length=200)

    workflow_file: str = Field(min_length=1)
    model_files: list[str] = Field(min_length=1)

    required_custom_nodes: list[str] = Field(default_factory=list)

    output_node_ids: list[str] = Field(min_length=1)

    injections: dict[str, InjectionTarget] = Field(min_length=4)

    enabled: bool = True


class ImageStudioConfig(BaseModel):
    version: str = "1.0.0"

    worker_concurrency: int = Field(
        default=1,
        ge=1,
        le=4
    )

    upload_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600
    )

    generation_timeout_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400
    )

    poll_interval_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=30
    )

    max_reference_size_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1024
    )

    max_image_dimension: int = Field(
        default=12000,
        ge=128,
        le=50000
    )

    comfyui_install_path: str | None = None
    custom_nodes_path: str | None = None
    models_path: str | None = None

    workflows_path: str = "comfyui_image_workflows"

    models: list[ImageModelConfig] = Field(default_factory=list)

    @field_validator("models")
    @classmethod
    def unique_model_ids(
        cls,
        models: list[ImageModelConfig]
    ) -> list[ImageModelConfig]:

        if len({model.model_id for model in models}) != len(models):
            raise ValueError("Image Studio model IDs must be unique")

        return models


def options_catalog() -> dict[str, list[str]]:
    """Public, schema-derived creative choices for UI/API contract checks."""

    return {
        "camera_angle": list(get_args(CameraAngle)),
        "shot_type": list(get_args(ShotType)),
        "pose": list(get_args(Pose)),
        "background": list(get_args(Background)),
        "lighting": list(get_args(Lighting)),
        "visual_style": list(get_args(VisualStyle)),
        "aspect_ratio": list(get_args(AspectRatio)),
        "number_of_images": [1, 2, 4, 8],
    }
