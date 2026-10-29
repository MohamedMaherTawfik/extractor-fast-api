"""FastAPI HTTP router for Social Content Intelligence Engine."""

from __future__ import annotations

import io
import os
import platform as sys_platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.db.base import utc_now
from backend.db.models.social_intelligence import (
    AnalysisEvidence,
    ContentAnalysisJob,
    ContentCopyAnalysis,
    ContentHookAnalysis,
    ContentNarrativeAnalysis,
    ContentTranscript,
    ContentVideoAnalysis,
    CreativeRecommendation,
    CreatorIntelligence,
    ExcelExportJob,
)
from backend.db.models.social_inventory import SocialInventoryItem
from backend.db.session import get_db
from backend.core.config import get_settings
from backend.social_intelligence.creator_dna import aggregate_creator_dna, compare_creators
from backend.social_intelligence.creative_generator import (
    GenerationRequest,
    generate_creative_recommendations,
)
from backend.social_intelligence.excel_exporter import export_intelligence_workbook
from backend.social_intelligence.schemas import (
    AnalysisJobResponse,
    BatchAnalysisRequest,
    CompleteContentAnalysisResponse,
    ContentSearchRequest,
    ContentSearchResponse,
    ContentSearchResultItem,
    CopyAnalysisResponse,
    CreativeGenerateRequest,
    CreativeRecommendationResponse,
    CreatorComparisonResponse,
    CreatorIntelligenceResponse,
    ExcelExportJobResponse,
    ExcelExportRequest,
    HookAnalysisResponse,
    NarrativeAnalysisResponse,
    TranscriptResponse,
    VideoAnalysisResponse,
)
from backend.social_intelligence.semantic_provider import get_semantic_provider
from backend.social_intelligence.worker import social_intelligence_worker

router = APIRouter(prefix="/social-intelligence", tags=["social-intelligence"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/analyze/{item_uuid}",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def analyze_single_item(
    item_uuid: UUID,
    session: DatabaseSession,
    force_reprocess: bool = Query(default=False),
    transcription_model: str | None = Query(default=None),
    semantic_model: str | None = Query(default=None),
    media_budget_seconds: int | None = Query(default=None, ge=5, le=7200),
):
    """Request end-to-end intelligence analysis for a single social inventory item."""
    item = session.query(SocialInventoryItem).filter_by(uuid=item_uuid).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Social inventory item not found")

    # Check for existing running or completed job
    existing = (
        session.query(ContentAnalysisJob)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentAnalysisJob.created_at.desc())
        .first()
    )

    if existing and not force_reprocess and existing.status in {"QUEUED", "PROCESSING", "COMPLETED"}:
        return existing

    job = ContentAnalysisJob(
        item_uuid=item_uuid,
        status="QUEUED",
        stage="QUEUED",
        progress_percent=0.0,
        options={
            key: value for key, value in {
                "transcription_model": transcription_model,
                "semantic_model": semantic_model,
                "media_budget_seconds": media_budget_seconds,
            }.items() if value is not None
        },
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    social_intelligence_worker.enqueue(job.uuid)
    return job


@router.post(
    "/analyze/batch",
    response_model=list[AnalysisJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def analyze_batch_items(
    request: BatchAnalysisRequest,
    session: DatabaseSession,
):
    """Submit a batch of content items for queued analysis."""
    settings = get_settings()
    if len(request.item_uuids) > settings.social_intelligence_batch_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds configured limit of {settings.social_intelligence_batch_limit} items",
        )
    jobs: list[ContentAnalysisJob] = []
    for item_uuid in request.item_uuids:
        item = session.query(SocialInventoryItem).filter_by(uuid=item_uuid).one_or_none()
        if not item:
            continue
        existing = (
            session.query(ContentAnalysisJob)
            .filter_by(item_uuid=item_uuid)
            .order_by(ContentAnalysisJob.created_at.desc())
            .first()
        )
        if existing and not request.force_reprocess and existing.status in {"QUEUED", "PROCESSING", "COMPLETED"}:
            jobs.append(existing)
            continue

        job = ContentAnalysisJob(
            item_uuid=item_uuid,
            status="QUEUED",
            stage="QUEUED",
            progress_percent=0.0,
            options={
                key: value for key, value in {
                    "transcription_model": request.transcription_model,
                    "semantic_model": request.semantic_model,
                    "media_budget_seconds": request.media_budget_seconds,
                }.items() if value is not None
            },
        )
        session.add(job)
        jobs.append(job)

    session.commit()
    for job in jobs:
        session.refresh(job)
        if job.status == "QUEUED":
            social_intelligence_worker.enqueue(job.uuid)

    return jobs


@router.get(
    "/jobs",
    response_model=list[AnalysisJobResponse],
)
def list_jobs(
    session: DatabaseSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
):
    """List background analysis jobs."""
    query = session.query(ContentAnalysisJob)
    if status_filter:
        query = query.filter(ContentAnalysisJob.status == status_filter.upper())
    return (
        query.order_by(ContentAnalysisJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/jobs/{job_uuid}",
    response_model=AnalysisJobResponse,
)
def get_job(
    job_uuid: UUID,
    session: DatabaseSession,
):
    """Get status and progress checkpoint for an analysis job."""
    job = session.query(ContentAnalysisJob).filter_by(uuid=job_uuid).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    return job


@router.post(
    "/jobs/{job_uuid}/retry",
    response_model=AnalysisJobResponse,
)
def retry_job(
    job_uuid: UUID,
    session: DatabaseSession,
):
    """Retry a failed or partial analysis job."""
    job = session.query(ContentAnalysisJob).filter_by(uuid=job_uuid).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if job.retry_count >= job.max_retries:
        raise HTTPException(status_code=409, detail="Maximum retry count reached")

    job.status = "QUEUED"
    job.stage = "QUEUED"
    job.progress_percent = 0.0
    job.retry_count += 1
    job.error_category = None
    job.error_message = None
    session.commit()
    session.refresh(job)

    social_intelligence_worker.enqueue(job.uuid)
    return job


@router.get(
    "/items/{item_uuid}",
    response_model=CompleteContentAnalysisResponse,
)
def get_complete_analysis(
    item_uuid: UUID,
    session: DatabaseSession,
):
    """Retrieve complete multi-modal analysis results for a content item."""
    item = session.query(SocialInventoryItem).filter_by(uuid=item_uuid).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Social inventory item not found")

    job = (
        session.query(ContentAnalysisJob)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentAnalysisJob.created_at.desc())
        .first()
    )

    t_resp = None
    h_resp = None
    c_resp = None
    s_resp = None
    v_resp = None
    evidence_resp = []

    if job:
        transcript = session.query(ContentTranscript).filter_by(job_id=job.id).first()
        if transcript:
            t_resp = TranscriptResponse.model_validate(transcript)

        hook = session.query(ContentHookAnalysis).filter_by(job_id=job.id).first()
        if hook:
            h_resp = HookAnalysisResponse.model_validate(hook)

        copy = session.query(ContentCopyAnalysis).filter_by(job_id=job.id).first()
        if copy:
            c_resp = CopyAnalysisResponse.model_validate(copy)

        narrative = session.query(ContentNarrativeAnalysis).filter_by(job_id=job.id).first()
        if narrative:
            s_resp = NarrativeAnalysisResponse.model_validate(narrative)

        video = session.query(ContentVideoAnalysis).filter_by(job_id=job.id).first()
        if video:
            v_resp = VideoAnalysisResponse.model_validate(video)
        evidence_resp = session.query(AnalysisEvidence).filter_by(job_id=job.id).order_by(AnalysisEvidence.id).all()

    return CompleteContentAnalysisResponse(
        item_uuid=item_uuid,
        job=AnalysisJobResponse.model_validate(job) if job else None,
        transcript=t_resp,
        hooks=h_resp,
        copy_analysis=c_resp,
        storytelling=s_resp,
        video=v_resp,
        evidence=evidence_resp,
    )


@router.get(
    "/items/{item_uuid}/transcript",
    response_model=TranscriptResponse,
)
def get_transcript(item_uuid: UUID, session: DatabaseSession):
    transcript = (
        session.query(ContentTranscript)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentTranscript.created_at.desc())
        .first()
    )
    if transcript is None:
        raise HTTPException(status_code=404, detail="No transcript available for this item")
    return TranscriptResponse.model_validate(transcript)


@router.get(
    "/items/{item_uuid}/hooks",
    response_model=HookAnalysisResponse,
)
def get_hooks(item_uuid: UUID, session: DatabaseSession):
    hook = (
        session.query(ContentHookAnalysis)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentHookAnalysis.created_at.desc())
        .first()
    )
    if hook is None:
        raise HTTPException(status_code=404, detail="No hook analysis available for this item")
    return HookAnalysisResponse.model_validate(hook)


@router.get(
    "/items/{item_uuid}/copy",
    response_model=CopyAnalysisResponse,
)
def get_copy(item_uuid: UUID, session: DatabaseSession):
    copy = (
        session.query(ContentCopyAnalysis)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentCopyAnalysis.created_at.desc())
        .first()
    )
    if copy is None:
        raise HTTPException(status_code=404, detail="No copy analysis available for this item")
    return CopyAnalysisResponse.model_validate(copy)


@router.get(
    "/items/{item_uuid}/video",
    response_model=VideoAnalysisResponse,
)
def get_video(item_uuid: UUID, session: DatabaseSession):
    video = (
        session.query(ContentVideoAnalysis)
        .filter_by(item_uuid=item_uuid)
        .order_by(ContentVideoAnalysis.created_at.desc())
        .first()
    )
    if video is None:
        raise HTTPException(status_code=404, detail="No video deconstruction available for this item")
    return VideoAnalysisResponse.model_validate(video)


@router.get(
    "/creators/{platform}/{username}",
    response_model=CreatorIntelligenceResponse,
)
def get_creator_dna(platform: str, username: str, session: DatabaseSession):
    """Retrieve aggregated creator profile and pattern intelligence."""
    intel = aggregate_creator_dna(session, platform=platform, username=username)
    session.commit()
    session.refresh(intel)
    return CreatorIntelligenceResponse.model_validate(intel)


@router.post(
    "/creative/generate",
    response_model=list[CreativeRecommendationResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_creative(
    payload: CreativeGenerateRequest,
    session: DatabaseSession,
):
    """Generate new original AI creative variations (hooks, captions, scripts)."""
    req = GenerationRequest(
        item_uuid=payload.item_uuid,
        creator_username=payload.creator_username,
        output_type=payload.output_type,
        target_platform=payload.target_platform,
        target_audience=payload.target_audience,
        target_duration=payload.target_duration,
        target_language=payload.target_language,
        objective=payload.objective,
        topic_context=payload.topic_context,
    )
    outputs = generate_creative_recommendations(session, req)
    session.commit()
    for o in outputs:
        session.refresh(o)
    return [CreativeRecommendationResponse.model_validate(o) for o in outputs]


@router.get(
    "/creative/items/{item_uuid}",
    response_model=list[CreativeRecommendationResponse],
)
def list_creative_recommendations(
    item_uuid: UUID,
    session: DatabaseSession,
):
    """List creative recommendations generated for a specific content item."""
    items = (
        session.query(CreativeRecommendation)
        .filter_by(item_uuid=item_uuid)
        .order_by(CreativeRecommendation.created_at.desc())
        .all()
    )
    return [CreativeRecommendationResponse.model_validate(i) for i in items]


@router.post(
    "/exports/excel",
    response_model=ExcelExportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_excel_export_job(
    req: ExcelExportRequest,
    session: DatabaseSession,
):
    """Generate a 14-sheet professional Excel export workbook."""
    file_path, filename = export_intelligence_workbook(
        session=session,
        item_uuids=req.item_uuids,
        creator_username=req.creator_username,
        filters=req.filters,
    )

    file_size = file_path.stat().st_size if file_path.exists() else 0
    export_job = ExcelExportJob(
        status="COMPLETED",
        scope=req.scope,
        filters=req.filters,
        file_path=str(file_path),
        filename=filename,
        file_size_bytes=file_size,
        completed_at=utc_now(),
    )
    session.add(export_job)
    session.commit()
    session.refresh(export_job)
    return ExcelExportJobResponse.model_validate(export_job)


@router.get(
    "/exports/excel/{export_uuid}/download",
)
def download_excel_export(
    export_uuid: UUID,
    session: DatabaseSession,
):
    """Download the generated Excel file by export job UUID."""
    job = session.query(ExcelExportJob).filter_by(uuid=export_uuid).one_or_none()
    if job is None or not job.file_path:
        raise HTTPException(status_code=404, detail="Export job not found")

    path = Path(job.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Exported file missing on server")

    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=job.filename or "social_content_intelligence.xlsx",
    )


@router.get(
    "/exports/excel/stream",
)
def stream_excel_export(
    session: DatabaseSession,
    creator_username: str | None = Query(default=None),
    scope: str = Query(default="all"),
):
    """Direct stream download of the 14-sheet professional Excel workbook."""
    file_path, filename = export_intelligence_workbook(
        session=session,
        creator_username=creator_username,
    )
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.get(
    "/capabilities",
)
def get_capabilities():
    """Return local host and processing capabilities (CPU, RAM, GPU, models)."""
    provider = get_semantic_provider()
    p_info = provider.get_provider_info()
    settings = get_settings()
    return {
        "status": "healthy",
        "system": {
            "os": sys_platform.system(),
            "cpu_cores": os.cpu_count(),
            "python_version": sys_platform.python_version(),
            "gpu_acceleration": settings.social_transcription_device == "cuda",
        },
        "ml_engines": {
            "transcription": f"faster-whisper-{settings.social_transcription_model} ({settings.social_transcription_device}/{settings.social_transcription_compute_type})",
            "video_vision": "No semantic vision model configured; PyAV/FFmpeg frame statistics and scene detection only",
            "semantic_provider": p_info.model_dump(),
        },
        "limits": {
            "max_concurrent_workers": settings.social_intelligence_max_workers,
            "max_batch_items": settings.social_intelligence_batch_limit,
            "media_budget_seconds": settings.social_intelligence_media_budget_seconds,
            "max_file_size_mb": 150,
            "default_timeout_seconds": 180,
        },
    }


@router.post(
    "/jobs/{job_uuid}/cancel",
)
def cancel_job(
    job_uuid: UUID,
):
    """Safely cancel an in-flight or enqueued analysis job."""
    success = social_intelligence_worker.cancel(job_uuid)
    return {"job_uuid": str(job_uuid), "cancelled": success}


@router.post(
    "/search",
    response_model=ContentSearchResponse,
)
def search_analyzed_content(
    criteria: ContentSearchRequest,
    session: DatabaseSession,
):
    """Structured search across completed content analyses."""
    query = session.query(SocialInventoryItem)

    # Filter platform
    if criteria.platform:
        query = query.filter(SocialInventoryItem.platform == criteria.platform)

    # Filter timeframe
    if criteria.date_from:
        query = query.filter(SocialInventoryItem.published_at >= criteria.date_from)
    if criteria.date_to:
        query = query.filter(SocialInventoryItem.published_at <= criteria.date_to)

    items = query.order_by(SocialInventoryItem.published_at.desc()).all()

    # In-memory evaluation of joined intelligence features
    results: list[ContentSearchResultItem] = []
    for item in items:
        # Check author
        author_user = (item.author or {}).get("username", "")
        if criteria.creator_username and author_user.lower() != criteria.creator_username.lower():
            continue

        # Get latest job
        job = (
            session.query(ContentAnalysisJob)
            .filter_by(item_uuid=item.uuid)
            .order_by(ContentAnalysisJob.created_at.desc())
            .first()
        )
        if not job:
            continue

        matched_hook = None
        matched_story = None
        matched_topic = None
        evidence_snippet = None

        # Check hook
        hook_db = session.query(ContentHookAnalysis).filter_by(job_id=job.id).first()
        if hook_db:
            if criteria.hook_category:
                if criteria.hook_category not in (hook_db.hook_types or []):
                    continue
            if hook_db.hook_types:
                matched_hook = hook_db.hook_types[0]
            if hook_db.spoken_hook and hook_db.spoken_hook.get("exact_text"):
                evidence_snippet = hook_db.spoken_hook["exact_text"][:100]

        # Check storytelling
        story_db = session.query(ContentNarrativeAnalysis).filter_by(job_id=job.id).first()
        if story_db:
            if criteria.storytelling_structure:
                if story_db.narrative_pattern != criteria.storytelling_structure:
                    continue
            matched_story = story_db.narrative_pattern

        # Check copy topic
        copy_db = session.query(ContentCopyAnalysis).filter_by(job_id=job.id).first()
        if copy_db:
            if criteria.topic:
                topic_q = criteria.topic.lower()
                m_top = (copy_db.main_topic or "").lower()
                s_top = " ".join(copy_db.secondary_topics or []).lower()
                if topic_q not in m_top and topic_q not in s_top:
                    continue
            matched_topic = copy_db.main_topic

        # Check video visual properties
        video_db = session.query(ContentVideoAnalysis).filter_by(job_id=job.id).first()
        if video_db:
            if criteria.has_talking_head is not None:
                if video_db.has_talking_head != criteria.has_talking_head:
                    continue
            if criteria.has_broll is not None:
                if video_db.has_broll != criteria.has_broll:
                    continue
            if criteria.min_duration and video_db.duration and video_db.duration < criteria.min_duration:
                continue
            if criteria.max_duration and video_db.duration and video_db.duration > criteria.max_duration:
                continue

        # Check transcript phrase
        if criteria.transcript_phrase:
            trans_db = session.query(ContentTranscript).filter_by(job_id=job.id).first()
            if not trans_db or criteria.transcript_phrase.lower() not in trans_db.full_text.lower():
                continue
            evidence_snippet = f"Transcript match: '{criteria.transcript_phrase}'"

        results.append(
            ContentSearchResultItem(
                item_uuid=item.uuid,
                platform=item.platform,
                author_username=author_user,
                title=item.title,
                caption_snippet=(item.caption or "")[:80],
                published_at=item.published_at,
                analysis_status=job.status,
                duration_seconds=video_db.duration if video_db else None,
                matched_hook_category=matched_hook,
                matched_storytelling_pattern=matched_story,
                matched_topic=matched_topic,
                evidence_snippet=evidence_snippet,
            )
        )

    total_matches = len(results)
    paged = results[criteria.offset : criteria.offset + criteria.limit]
    return ContentSearchResponse(total=total_matches, results=paged)


@router.get(
    "/creators/compare",
    response_model=CreatorComparisonResponse,
)
def compare_creators_endpoint(
    session: DatabaseSession,
    usernames: str = Query(description="Comma-separated creator usernames, e.g. eldaheeh,creator2"),
    platform: str = Query(default="instagram"),
):
    """Side-by-side comparison of 2 or more creators within the same platform."""
    user_list = [u.strip() for u in usernames.split(",") if u.strip()]
    if not user_list:
        raise HTTPException(status_code=400, detail="At least one creator username is required")

    comp_res = compare_creators(session=session, platform=platform, usernames=user_list)
    session.commit()
    return comp_res
