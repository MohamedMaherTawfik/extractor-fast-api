"""Creator Discovery Studio API."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.creator_discovery.input import parse_creator_input
from backend.creator_discovery.service import CreatorDiscoveryService
from backend.db.session import get_db
from backend.schemas.creator_discovery import (
    CandidateDecisionRequest,
    ConnectorCapabilityResponse,
    CreatorCandidateResponse,
    CreatorDiscoveryRunRequest,
    CreatorDiscoveryRunResponse,
    CreatorExportRequest,
    CreatorProfileUpdate,
    CreatorRefreshRequest,
    DiscoveryPlatform,
)


router = APIRouter(tags=["creator-discovery-studio"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/creator-discovery/connectors",
    response_model=list[ConnectorCapabilityResponse],
)
def connector_capabilities(session: DatabaseSession):
    return CreatorDiscoveryService(session).connector_capabilities()


@router.get("/creator-discovery/meta/status")
def meta_connection_status(session: DatabaseSession):
    return CreatorDiscoveryService(session).meta_connection_status()


@router.post("/creator-discovery/meta/validate")
def validate_meta_connection(session: DatabaseSession):
    return CreatorDiscoveryService(session).meta_connection_status(force=True)


@router.get("/creator-discovery/industries")
def industries(session: DatabaseSession):
    return CreatorDiscoveryService(session).industries()


@router.post(
    "/creator-discovery/runs",
    response_model=CreatorDiscoveryRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_run(request: CreatorDiscoveryRunRequest, session: DatabaseSession):
    try:
        return CreatorDiscoveryService(session).create_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/creator-discovery/runs/import",
    response_model=CreatorDiscoveryRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_run(
    session: DatabaseSession,
    file: UploadFile = File(...),
    platforms: str = Form(...),
    analyze_content: bool = Form(True),
    resolve_cross_platform_identity: bool = Form(True),
    update_existing_profiles: bool = Form(False),
    content_sample_size: int = Form(10),
    execute: bool = Form(True),
):
    content = await file.read()
    if len(content) > get_settings().import_max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Creator input file is too large")
    try:
        platform_values = [DiscoveryPlatform(value) for value in json.loads(platforms)]
        inputs = parse_creator_input(
            file.filename or "creator-input.csv",
            content,
            limit=get_settings().import_max_file_size_mb * 400,
        )
        request = CreatorDiscoveryRunRequest(
            inputs=inputs,
            platforms=platform_values,
            analyze_content=analyze_content,
            resolve_cross_platform_identity=resolve_cross_platform_identity,
            update_existing_profiles=update_existing_profiles,
            content_sample_size=content_sample_size,
            execute=execute,
        )
        return CreatorDiscoveryService(session).create_run(request)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/creator-discovery/runs")
def list_runs(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    return CreatorDiscoveryService(session).list_runs(offset, limit)


@router.get(
    "/creator-discovery/runs/{run_uid}",
    response_model=CreatorDiscoveryRunResponse,
)
def get_run(run_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).get_run(run_uid)


@router.post("/creator-discovery/runs/{run_uid}/pause", response_model=CreatorDiscoveryRunResponse)
def pause_run(run_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).pause_run(run_uid)


@router.post("/creator-discovery/runs/{run_uid}/resume", response_model=CreatorDiscoveryRunResponse)
def resume_run(run_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).resume_run(run_uid)


@router.post("/creator-discovery/runs/{run_uid}/retry", response_model=CreatorDiscoveryRunResponse)
def retry_run(run_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).retry_run(run_uid)


@router.post("/creator-discovery/runs/{run_uid}/cancel", response_model=CreatorDiscoveryRunResponse)
def cancel_run(run_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).cancel_run(run_uid)


@router.get("/creator-discovery/candidates")
def list_candidates(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    run_uid: str | None = None,
    platform: DiscoveryPlatform | None = None,
    review_status: str | None = None,
    classification: str | None = None,
):
    return CreatorDiscoveryService(session).list_candidates(
        offset=offset, limit=limit, run_uid=run_uid,
        platform=platform.value if platform else None,
        review_status=review_status, classification=classification,
    )


@router.get("/creator-discovery/candidates/{candidate_uid}")
def candidate_detail(candidate_uid: str, session: DatabaseSession):
    service = CreatorDiscoveryService(session)
    candidate = service._candidate(candidate_uid)
    payload = CreatorCandidateResponse.model_validate(candidate).model_dump(mode="json")
    payload["match_evidence"] = [{
        "signal": item.signal, "score": item.score, "weight": item.weight,
        "contribution": item.contribution, "evidence": item.evidence,
    } for item in candidate.match_evidence]
    return payload


@router.post("/creator-discovery/candidates/{candidate_uid}/confirm")
def confirm_candidate(
    candidate_uid: str,
    decision: CandidateDecisionRequest,
    session: DatabaseSession,
):
    return CreatorDiscoveryService(session).confirm_candidate(candidate_uid, decision)


@router.post(
    "/creator-discovery/candidates/{candidate_uid}/reject",
    response_model=CreatorCandidateResponse,
)
def reject_candidate(candidate_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).reject_candidate(candidate_uid)


@router.get("/creator-discovery/creators")
def list_profiles(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    q: Annotated[str | None, Query(max_length=200)] = None,
    platform: DiscoveryPlatform | None = None,
    industry: str | None = None,
    niche: str | None = None,
    influence_min: int | None = Query(None, ge=0),
    influence_max: int | None = Query(None, ge=0),
    match_confidence_min: float | None = Query(None, ge=0, le=100),
    analysis_status: str | None = None,
    start_year: int | None = Query(None, ge=1900, le=2100),
):
    return CreatorDiscoveryService(session).list_profiles(
        offset=offset, limit=limit, query=q,
        platform=platform.value if platform else None, industry=industry, niche=niche,
        influence_min=influence_min, influence_max=influence_max,
        match_confidence_min=match_confidence_min, analysis_status=analysis_status,
        start_year=start_year, creator_uids=None,
    )


@router.get("/creator-discovery/creators/{profile_uid}")
def profile_detail(profile_uid: str, session: DatabaseSession):
    return CreatorDiscoveryService(session).profile_detail(profile_uid)


@router.patch("/creator-discovery/creators/{profile_uid}")
def update_profile(profile_uid: str, update: CreatorProfileUpdate, session: DatabaseSession):
    try:
        return CreatorDiscoveryService(session).update_profile(profile_uid, update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/creator-discovery/creators/{profile_uid}/refresh")
def refresh_profile(profile_uid: str, request: CreatorRefreshRequest, session: DatabaseSession):
    return CreatorDiscoveryService(session).refresh_profile(profile_uid, request)


@router.post("/creators/export")
@router.post("/creator-discovery/export")
def export_creators(request: CreatorExportRequest, session: DatabaseSession):
    content, media_type, filename = CreatorDiscoveryService(session).export(request)
    return StreamingResponse(
        BytesIO(content), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
