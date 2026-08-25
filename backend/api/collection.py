"""Universal collector API; execution can later move behind a worker."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.connectors.registry import connector_registry
from backend.db.session import get_db
from backend.schemas.collection import (
    CollectionOptions,
    CollectionRunResponse,
    ManualURLCollectionRequest,
)
from backend.services.content_collector import UniversalContentCollector


router = APIRouter(tags=["collection"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/connectors/status", response_model=dict[str, str])
def connector_statuses() -> dict[str, str]:
    return connector_registry.statuses()


@router.post(
    "/collection/creator/{creator_id}",
    response_model=list[CollectionRunResponse],
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/collection/creators/{creator_id}",
    response_model=list[CollectionRunResponse],
    status_code=status.HTTP_201_CREATED,
)
def collect_creator(
    creator_id: int,
    options: CollectionOptions,
    session: DatabaseSession,
):
    return UniversalContentCollector(session).collect_creator(creator_id, options)


@router.post(
    "/collection/account/{account_id}",
    response_model=CollectionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/collection/platform-accounts/{account_id}",
    response_model=CollectionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def collect_platform_account(
    account_id: int,
    options: CollectionOptions,
    session: DatabaseSession,
):
    return UniversalContentCollector(session).collect_account(account_id, options)


@router.post(
    "/collection/url",
    response_model=CollectionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def collect_url(data: ManualURLCollectionRequest, session: DatabaseSession):
    options = CollectionOptions.model_validate(data.model_dump(exclude={"url"}))
    return UniversalContentCollector(session).collect_url(data.url, options)


@router.get("/collection/jobs", response_model=list[CollectionRunResponse])
def list_collection_jobs(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return UniversalContentCollector(session).list_runs(offset=offset, limit=limit)


@router.get("/collection/jobs/{run_id}", response_model=CollectionRunResponse)
def get_collection_job(run_id: int, session: DatabaseSession):
    return UniversalContentCollector(session).get_run(run_id)
