"""API surface for the dedicated ComfyUI-backed AI Video Studio."""

from __future__ import annotations

from functools import lru_cache
import json
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from backend.core.config import get_settings
from backend.generation.video_engine.schemas import BatchGenerationRequest, VideoGenerationRequest
from backend.generation.video_engine.video_generator import VideoGenerator


router = APIRouter(prefix="/video-studio", tags=["ai-video-studio"])


@lru_cache(maxsize=1)
def get_video_generator() -> VideoGenerator:
    engine = VideoGenerator()
    engine.recover_pending()
    return engine


def _json_object(value: str, field: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail=f"{field} must be a JSON object")
    return parsed


def _json_list(value: str, field: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be valid JSON") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(status_code=422, detail=f"{field} must be a JSON list of strings")
    return parsed


@router.get("/config")
def studio_config():
    engine = get_video_generator()
    return {
        "version": engine.config.version,
        "provider": "comfyui",
        "comfyui_configured": bool(get_settings().comfyui_base_url),
        "default_model": engine.config.default_model,
        "models": engine.router.public_models(),
        "recipes": [
            {
                "recipe_id": item.recipe_id, "name": item.name,
                "camera_style": item.camera_style, "lighting": item.lighting,
                "colors": item.colors, "environment": item.environment,
                "realism_level": item.realism_level, "motion_style": item.motion_style,
            }
            for item in engine.config.recipes
        ],
        "worker": {"concurrency": engine.config.worker_concurrency, "active_jobs": engine.worker.active_jobs()},
    }


@router.post("/characters", status_code=status.HTTP_201_CREATED)
async def create_character(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    identity_data: Annotated[str, Form()] = "{}",
    style_profile: Annotated[str, Form()] = "{}",
    recurring_attributes: Annotated[str, Form()] = "[]",
    negative_constraints: Annotated[str, Form()] = "[]",
):
    engine = get_video_generator()
    content = await file.read(engine.config.max_reference_size_bytes + 1)
    return engine.characters.create(
        name=name, image=content, mime_type=file.content_type or "application/octet-stream",
        identity_data=_json_object(identity_data, "identity_data"),
        style_profile=_json_object(style_profile, "style_profile"),
        recurring_attributes=_json_list(recurring_attributes, "recurring_attributes"),
        negative_constraints=_json_list(negative_constraints, "negative_constraints"),
    )


@router.get("/characters")
def list_characters():
    return get_video_generator().characters.list()


@router.get("/characters/{character_id}")
def get_character(character_id: str):
    return get_video_generator().characters.get(character_id)


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def generate_video(request: VideoGenerationRequest):
    return get_video_generator().create(request)


@router.get("/jobs")
def list_video_jobs(limit: int = Query(100, ge=1, le=1000), batch_id: str | None = None):
    return get_video_generator().assets.list_jobs(limit=limit, batch_id=batch_id)


@router.get("/jobs/{job_id}")
def get_video_job(job_id: str):
    return get_video_generator().assets.get_job(job_id)


@router.post("/jobs/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_video_job(job_id: str):
    engine = get_video_generator()
    job = engine.assets.get_job(job_id)
    engine.worker.submit(job_id, lambda: engine.run(job_id))
    return job


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_video_job(job_id: str):
    return get_video_generator().retry(job_id)


@router.post("/jobs/{job_id}/cancel")
def cancel_video_job(job_id: str):
    return get_video_generator().cancel(job_id)


@router.post("/batches", status_code=status.HTTP_202_ACCEPTED)
def create_video_batch(request: BatchGenerationRequest):
    return get_video_generator().create_batch(request)


@router.get("/batches")
def list_video_batches(limit: int = Query(100, ge=1, le=1000)):
    engine = get_video_generator()
    return [engine.batch_status(item.batch_id) for item in engine.assets.list_batches(limit)]


@router.get("/batches/{batch_id}")
def get_video_batch(batch_id: str):
    return get_video_generator().batch_status(batch_id)


@router.get("/assets")
def list_video_assets(limit: int = Query(100, ge=1, le=1000)):
    return get_video_generator().assets.list_assets(limit)


@router.get("/assets/{asset_id}")
def get_video_asset(asset_id: str, version: int | None = Query(None, ge=1)):
    return get_video_generator().assets.get_asset(asset_id, version)


@router.get("/assets/{asset_id}/content", response_class=FileResponse)
def video_asset_content(asset_id: str, version: int | None = Query(None, ge=1)):
    target, record = get_video_generator().assets.asset_path(asset_id, version)
    return FileResponse(target, media_type=record["mime_type"], filename=target.name)


@router.post("/assets/{asset_id}/save")
def save_video_asset(asset_id: str):
    return get_video_generator().assets.mark_saved(asset_id)
