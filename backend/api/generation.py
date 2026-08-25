"""Contract-first local APIs for generation orchestration and asset inspection."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.core.exceptions import NotFoundError
from backend.generation.orchestrator import GenerationOrchestrator
from backend.repositories.generation_repository import GenerationRepository
from backend.schemas.generation import (
    AssetArchiveRequest, GeneratedAssetResponse, GenerationCancelRequest,
    GenerationJobResponse, GenerationPreviewResponse, GenerationRequest,
    ModelProfileResponse, AssetVersionResponse,
)


router = APIRouter(tags=["generation"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _job(item):
    return GenerationJobResponse.model_validate(item)


@router.post("/generation/preview", response_model=GenerationPreviewResponse)
def preview_generation(request: GenerationRequest, session: DatabaseSession):
    return GenerationOrchestrator(session).preview_job(request)


@router.post("/generation/jobs", status_code=status.HTTP_201_CREATED)
def create_generation_job(request: GenerationRequest, session: DatabaseSession):
    result = GenerationOrchestrator(session).create_job(request)
    if isinstance(result, GenerationPreviewResponse):
        return result
    return _job(result)


@router.get("/generation/jobs", response_model=list[GenerationJobResponse])
def list_generation_jobs(session: DatabaseSession, job_status: str | None = Query(None, alias="status"), limit: int = Query(100, ge=1, le=1000)):
    return [_job(item) for item in GenerationOrchestrator(session).list_jobs(status=job_status, limit=limit)]


@router.get("/generation/jobs/{job_id}", response_model=GenerationJobResponse)
def get_generation_job(job_id: str, session: DatabaseSession):
    return _job(GenerationOrchestrator(session).get_status(job_id))


@router.post("/generation/jobs/{job_id}/run", response_model=GenerationJobResponse)
def run_generation_job(job_id: str, session: DatabaseSession):
    return _job(GenerationOrchestrator(session).run_job(job_id))


@router.post("/generation/jobs/{job_id}/retry", response_model=GenerationJobResponse)
def retry_generation_job(job_id: str, session: DatabaseSession):
    return _job(GenerationOrchestrator(session).retry_job(job_id))


@router.post("/generation/jobs/{job_id}/cancel", response_model=GenerationJobResponse)
def cancel_generation_job(job_id: str, request: GenerationCancelRequest, session: DatabaseSession):
    return _job(GenerationOrchestrator(session).cancel_job(job_id, cancelled_by=request.cancelled_by, reason=request.reason))


def _generate(request: GenerationRequest, session: Session):
    result = GenerationOrchestrator(session).create_job(request)
    return result if isinstance(result, GenerationPreviewResponse) else _job(result)


@router.post("/generation/copy")
def generate_copy(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.post("/generation/image")
def generate_image(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.post("/generation/video")
def generate_video(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.post("/generation/audio")
def generate_audio(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.post("/generation/storyboard")
def generate_storyboard(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.post("/generation/from-recipe")
def generate_from_recipe_contract(request: GenerationRequest, session: DatabaseSession): return _generate(request, session)


@router.get("/generation/providers")
def list_generation_providers(session: DatabaseSession):
    orchestrator = GenerationOrchestrator(session)
    return [{
        "provider_code": item.provider_code, "display_name": item.display_name,
        "locality": item.locality, "enabled": item.enabled, "availability": item.availability,
        "health": orchestrator.providers.health(item.provider_code),
    } for item in GenerationRepository(session).list_providers()]


@router.get("/generation/models", response_model=list[ModelProfileResponse])
def list_generation_models(session: DatabaseSession):
    return GenerationOrchestrator(session).models.list_models()


@router.get("/assets/{asset_id}", response_model=GeneratedAssetResponse)
def get_generated_asset(asset_id: str, session: DatabaseSession):
    asset = GenerationOrchestrator(session).repository.get_asset(asset_id)
    if asset is None: raise NotFoundError(f"Generated asset {asset_id} was not found")
    return GeneratedAssetResponse.model_validate(asset)


@router.get("/assets/{asset_id}/versions")
def get_asset_versions(asset_id: str, session: DatabaseSession):
    asset = GenerationOrchestrator(session).repository.get_asset(asset_id)
    if asset is None: raise NotFoundError(f"Generated asset {asset_id} was not found")
    return [AssetVersionResponse.model_validate(item) for item in asset.versions]


@router.get("/assets/{asset_id}/provenance")
def get_asset_provenance(asset_id: str, session: DatabaseSession):
    repository = GenerationRepository(session)
    asset = repository.get_asset(asset_id)
    if asset is None: raise NotFoundError(f"Generated asset {asset_id} was not found")
    return [{
        "provenance_uid": item.provenance_uid, "contract_id": item.contract_id,
        "contract_version": item.contract_version, "recipe_id": item.recipe_id,
        "recipe_version": item.recipe_version, "provider": item.provider,
        "model_id": item.model_id, "model_version": item.model_version,
        "seed": item.seed, "references": item.reference_asset_ids, "c2pa_status": item.c2pa_status,
    } for item in repository.provenance_for_asset(asset)]


@router.post("/assets/{asset_id}/approve", response_model=GeneratedAssetResponse)
def approve_asset(asset_id: str, session: DatabaseSession):
    return GeneratedAssetResponse.model_validate(GenerationOrchestrator(session).finalize_asset(asset_id))


@router.post("/assets/{asset_id}/archive", response_model=GeneratedAssetResponse)
def archive_asset(asset_id: str, request: AssetArchiveRequest, session: DatabaseSession):
    orchestrator = GenerationOrchestrator(session)
    asset = orchestrator.repository.get_asset(asset_id)
    if asset is None: raise NotFoundError(f"Generated asset {asset_id} was not found")
    orchestrator.storage.archive(asset, reason=request.reason)
    orchestrator._event(asset.job, "ASSET_ARCHIVED", {"asset_uid": asset.asset_uid, "reason": request.reason})
    return GeneratedAssetResponse.model_validate(asset)
