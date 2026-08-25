"""Local API for versioned content and batch analysis jobs."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.analysis import (
    AnalysisBatchRequest,
    AnalysisOptions,
    AnalysisRunResponse,
    ContentAnalysisResponse,
)
from backend.services.analysis_service import UniversalContentAnalyzer


router = APIRouter(tags=["analysis"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/analysis/content/{content_id}",
    response_model=AnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_content(
    content_id: str,
    session: DatabaseSession,
    options: AnalysisOptions | None = None,
):
    return UniversalContentAnalyzer(session).analyze_content(content_id, options)


@router.post(
    "/analysis/batch",
    response_model=list[AnalysisRunResponse],
    status_code=status.HTTP_201_CREATED,
)
def analyze_batch(request: AnalysisBatchRequest, session: DatabaseSession):
    return UniversalContentAnalyzer(session).analyze_batch(request)


@router.get(
    "/analysis/jobs/{job_id}",
    response_model=AnalysisRunResponse,
)
def get_analysis_job(job_id: str, session: DatabaseSession):
    return UniversalContentAnalyzer(session).get_run(job_id)


@router.get(
    "/analysis/content/{content_id}",
    response_model=ContentAnalysisResponse,
)
def get_content_analysis(content_id: str, session: DatabaseSession):
    return UniversalContentAnalyzer(session).get_content_analysis(content_id)
