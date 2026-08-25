"""API for Content DNA, deterministic similarity, and pattern mining."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.pattern_recipe import (
    ContentDNAResponse,
    ContentClusterRequest,
    ContentClusterResponse,
    DNABatchRequest,
    DNABatchResponse,
    DNASimilarityResponse,
    PatternDetailResponse,
    PatternMineRequest,
    PatternMiningRunResponse,
    PatternResponse,
    SimilarContentItem,
)
from backend.services.content_dna_service import ContentDNAService
from backend.services.content_similarity_service import ContentSimilarityService
from backend.services.pattern_mining_service import PatternMiningService


router = APIRouter(tags=["patterns"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/content/{content_id}/dna", response_model=ContentDNAResponse, status_code=status.HTTP_201_CREATED)
def generate_content_dna(content_id: str, session: DatabaseSession):
    return ContentDNAService(session).generate(content_id)


@router.post("/content/dna/batch", response_model=DNABatchResponse, status_code=status.HTTP_201_CREATED)
def generate_content_dna_batch(request: DNABatchRequest, session: DatabaseSession):
    return ContentDNAService(session).generate_batch(request.content_ids)


@router.get("/content/{content_id}/dna", response_model=ContentDNAResponse)
def get_content_dna(content_id: str, session: DatabaseSession):
    return ContentDNAService(session).get(content_id)


@router.get("/content/{content_id}/compare/{other_content_id}", response_model=DNASimilarityResponse)
def compare_content_dna(content_id: str, other_content_id: str, session: DatabaseSession):
    return ContentSimilarityService(session).compare(content_id, other_content_id)


@router.get("/content/{content_id}/similar", response_model=list[SimilarContentItem])
def similar_content(
    content_id: str,
    session: DatabaseSession,
    limit: int = Query(default=10, ge=1, le=100),
):
    return ContentSimilarityService(session).similar(content_id, limit=limit)


@router.post("/content/clusters", response_model=list[ContentClusterResponse])
def cluster_content(request: ContentClusterRequest, session: DatabaseSession):
    return ContentSimilarityService(session).cluster(request)


@router.post("/patterns/mine", response_model=PatternMiningRunResponse, status_code=status.HTTP_201_CREATED)
def mine_patterns(request: PatternMineRequest, session: DatabaseSession):
    return PatternMiningService(session).mine(request)


@router.get("/patterns", response_model=list[PatternResponse])
def list_patterns(
    session: DatabaseSession,
    pattern_type: str | None = None,
    pattern_status: str | None = Query(default=None, alias="status"),
    platform: str | None = None,
    content_type: str | None = None,
    creator_id: int | None = None,
    category: str | None = None,
    language: str | None = None,
    country: str | None = None,
    traffic_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    return PatternMiningService(session).list(
        pattern_type=pattern_type,
        status=pattern_status,
        platform=platform,
        content_type=content_type,
        creator_id=creator_id,
        category=category,
        language=language,
        country=country,
        traffic_type=traffic_type,
        limit=limit,
    )


@router.get("/patterns/top", response_model=list[PatternResponse])
def top_patterns(
    session: DatabaseSession,
    platform: str | None = None,
    content_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    return PatternMiningService(session).list(
        platform=platform, content_type=content_type, limit=limit, top=True
    )


@router.get("/patterns/{pattern_id}", response_model=PatternDetailResponse)
def get_pattern(pattern_id: str, session: DatabaseSession):
    return PatternMiningService(session).explain(pattern_id)
