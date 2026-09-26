"""HTTP API for the capability-aware AI Product Image Studio."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response

from backend.image_studio.prompting import preset_catalog
from backend.image_studio.schemas import ImageStudioSettings, options_catalog
from backend.image_studio.service import ImageStudioService


router = APIRouter(prefix="/image-studio", tags=["ai-product-image-studio"])


@lru_cache(maxsize=1)
def get_image_studio() -> ImageStudioService:
    engine = ImageStudioService()
    engine.recover_pending()
    return engine


def _settings(value: str) -> ImageStudioSettings:
    try:
        return ImageStudioSettings.model_validate(json.loads(value))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="settings must be a valid Image Studio settings object") from exc


@router.get("/capabilities")
def capabilities():
    return get_image_studio().capabilities.report()


@router.get("/health")
def health():
    """Return the live local ComfyUI health and generation-readiness report."""
    return get_image_studio().capabilities.report()


@router.get("/models")
def models():
    return get_image_studio().capabilities.report()["models"]


@router.get("/presets")
def presets():
    return preset_catalog()


@router.get("/options")
def options():
    """Authoritative creative-option catalog derived from the request schema."""
    return options_catalog()


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    character_image: Annotated[UploadFile, File()],
    product_image: Annotated[UploadFile, File()],
    settings: Annotated[str, Form()],
):
    engine = get_image_studio()
    limit = engine.config.max_reference_size_bytes + 1
    character_content = await character_image.read(limit)
    product_content = await product_image.read(limit)
    job = engine.create(
        character_filename=character_image.filename, character_mime=character_image.content_type, character_content=character_content,
        product_filename=product_image.filename, product_mime=product_image.content_type, product_content=product_content,
        settings=_settings(settings),
    )
    return {"job_id": job.job_id, "status": "QUEUED"}


@router.get("/jobs")
def list_jobs(limit: int = Query(100, ge=1, le=1000)):
    return get_image_studio().storage.list_jobs(limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    return get_image_studio().storage.get_job(job_id)


@router.post("/jobs/{job_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
def regenerate(job_id: str, same_seed: bool = False):
    job = get_image_studio().regenerate(job_id, same_seed=same_seed)
    return {"job_id": job.job_id, "status": "QUEUED"}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return get_image_studio().cancel(job_id)


@router.get("/assets/{asset_id}/content")
def asset_content(asset_id: str):
    target, record = get_image_studio().storage.asset_path(asset_id)
    return FileResponse(target, media_type=str(record["mime_type"]), filename=str(record["filename"]))


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: str):
    get_image_studio().storage.delete_asset(asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
