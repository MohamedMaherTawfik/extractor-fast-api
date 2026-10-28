"""Authenticated-local Social Inventory HTTP API and safe exports."""

import asyncio
import csv
import io
import json
import tempfile
from datetime import UTC, datetime
from typing import Annotated, Iterator, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db.session import get_db
from backend.social_inventory.exceptions import SocialInventoryError, feature_disabled
from backend.social_inventory.providers.apify import ApifyProvider
from backend.social_inventory.providers.jev import JevSocialProvider
from backend.social_inventory.repository import SocialInventoryRepository
from backend.social_inventory.schemas import ItemResponse, PaginatedItems, ResearchRequest, RunResponse, SourceCreate, SourceResponse, SourceUpdate
from backend.social_inventory.service import SocialInventoryService

router = APIRouter(prefix="/social-inventory", tags=["social-inventory"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def current_owner() -> str:
    # The existing desktop application has one trusted local operator and no login
    # system. Keeping this dependency explicit makes tenant auth replaceable later.
    return "local-operator"


Owner = Annotated[str, Depends(current_owner)]


def _repo(session: Session, owner: str) -> SocialInventoryRepository:
    if not get_settings().social_inventory_enabled: raise feature_disabled()
    return SocialInventoryRepository(session, owner)


def _source_or_404(repo: SocialInventoryRepository, value: UUID):
    item = repo.get_source(value)
    if item is None: raise SocialInventoryError("SOCIAL_SOURCE_NOT_FOUND", "Social source was not found.", status_code=404)
    return item


def _run_or_404(repo: SocialInventoryRepository, value: UUID):
    item = repo.get_run(value)
    if item is None: raise SocialInventoryError("SOCIAL_RUN_NOT_FOUND", "Social run was not found.", status_code=404)
    return item


async def _capabilities():
    settings = get_settings()
    if not settings.social_inventory_enabled: raise feature_disabled()
    provider = ApifyProvider(settings)
    try:
        apify = await provider.capabilities()
        return {"apify": apify.model_dump(), "jev": JevSocialProvider(settings).capability(), "limits": {"max_items": settings.social_inventory_max_items, "max_comments_per_post": settings.social_inventory_max_comments_per_post}}
    finally:
        await provider.close()


@router.get("/capabilities")
async def capabilities():
    return await _capabilities()


@router.get("/overview")
def overview(session: DatabaseSession, owner: Owner): return _repo(session, owner).overview()


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(session: DatabaseSession, owner: Owner): return _repo(session, owner).list_sources()


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source(data: SourceCreate, request: Request, session: DatabaseSession, owner: Owner):
    source, run = SocialInventoryService(session, owner).create_source_and_run(data, request.headers.get("X-Request-ID"))
    return {"source": SourceResponse.model_validate(source), "run": RunResponse.model_validate(run)}


@router.get("/sources/{source_uuid}", response_model=SourceResponse)
def get_source(source_uuid: UUID, session: DatabaseSession, owner: Owner): return _source_or_404(_repo(session, owner), source_uuid)


@router.patch("/sources/{source_uuid}", response_model=SourceResponse)
def update_source(source_uuid: UUID, data: SourceUpdate, session: DatabaseSession, owner: Owner):
    service = SocialInventoryService(session, owner); return service.update_source(_source_or_404(service.repo, source_uuid), data)


@router.post("/sources/{source_uuid}/sync", response_model=RunResponse, status_code=202)
def sync_source(source_uuid: UUID, request: Request, session: DatabaseSession, owner: Owner):
    service = SocialInventoryService(session, owner); return service.sync(_source_or_404(service.repo, source_uuid), request.headers.get("X-Request-ID"))


@router.get("/runs", response_model=list[RunResponse])
def list_runs(session: DatabaseSession, owner: Owner, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 100): return _repo(session, owner).list_runs(offset, limit)


@router.get("/runs/{run_uuid}", response_model=RunResponse)
def get_run(run_uuid: UUID, session: DatabaseSession, owner: Owner): return _run_or_404(_repo(session, owner), run_uuid)


@router.post("/runs/{run_uuid}/cancel", response_model=RunResponse)
def cancel_run(run_uuid: UUID, session: DatabaseSession, owner: Owner):
    service = SocialInventoryService(session, owner); return service.cancel(_run_or_404(service.repo, run_uuid))


@router.post("/runs/{run_uuid}/retry", response_model=RunResponse)
def retry_run(run_uuid: UUID, session: DatabaseSession, owner: Owner):
    service = SocialInventoryService(session, owner); return service.retry(_run_or_404(service.repo, run_uuid))


def _item_query(repo, offset, limit, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort):
    return repo.list_items(offset=offset, limit=limit, platform=platform, source_id=source_id, content_type=content_type, keyword=keyword, date_from=date_from, date_to=date_to, min_engagement=min_engagement, sort=sort)


@router.get("/items", response_model=PaginatedItems)
def list_items(session: DatabaseSession, owner: Owner, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 100, platform: str | None = None, source_id: int | None = None, content_type: str | None = None, keyword: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, min_engagement: int | None = Query(default=None, ge=0), sort: str = "newest"):
    items, total = _item_query(_repo(session, owner), offset, limit, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/items/{item_uuid}", response_model=ItemResponse)
def get_item(item_uuid: UUID, session: DatabaseSession, owner: Owner):
    item = _repo(session, owner).get_item(item_uuid)
    if item is None: raise SocialInventoryError("SOCIAL_SOURCE_NOT_FOUND", "Social item was not found.", status_code=404)
    return item


HEADERS = ["platform", "external_id", "canonical_url", "content_type", "title", "caption", "published_at", "username", "views", "likes", "comments", "shares", "saves"]


def _safe(value):
    if value is None: return ""
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def _row(item) -> list:
    metrics, author = item.metrics or {}, item.author or {}
    return [item.platform, item.external_id, item.canonical_url, item.content_type, item.title, item.caption, item.published_at.isoformat() if item.published_at else "", author.get("username"), metrics.get("views"), metrics.get("likes"), metrics.get("comments"), metrics.get("shares"), metrics.get("saves")]


def _all_filtered(repo, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort) -> Iterator:
    offset, page = 0, get_settings().social_inventory_page_size
    while True:
        items, _ = repo.list_items(offset=offset, limit=page, platform=platform, source_id=source_id, content_type=content_type, keyword=keyword, date_from=date_from, date_to=date_to, min_engagement=min_engagement, sort=sort)
        yield from items
        if len(items) < page: break
        offset += len(items)


def _filename(platform: str | None, extension: str) -> str:
    return f"social-inventory-{platform or 'all'}-{datetime.now(UTC).date().isoformat()}.{extension}"


@router.get("/exports/csv")
def export_csv(session: DatabaseSession, owner: Owner, platform: str | None = None, source_id: int | None = None, content_type: str | None = None, keyword: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, min_engagement: int | None = None, sort: str = "newest"):
    repo = _repo(session, owner)
    def stream():
        output = io.StringIO(); writer = csv.writer(output); writer.writerow(HEADERS); yield output.getvalue(); output.seek(0); output.truncate(0)
        for item in _all_filtered(repo, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort):
            writer.writerow([_safe(v) for v in _row(item)]); yield output.getvalue(); output.seek(0); output.truncate(0)
    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{_filename(platform, "csv")}"'})


@router.get("/exports/json")
def export_json(session: DatabaseSession, owner: Owner, platform: str | None = None, source_id: int | None = None, content_type: str | None = None, keyword: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, min_engagement: int | None = None, sort: str = "newest"):
    repo = _repo(session, owner)
    def stream():
        yield "["; first = True
        for item in _all_filtered(repo, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort):
            if not first: yield ","
            first = False; yield json.dumps(ItemResponse.model_validate(item).model_dump(mode="json"), ensure_ascii=False)
        yield "]"
    return StreamingResponse(stream(), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{_filename(platform, "json")}"'})


@router.get("/exports/xlsx")
def export_xlsx(session: DatabaseSession, owner: Owner, platform: str | None = None, source_id: int | None = None, content_type: str | None = None, keyword: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, min_engagement: int | None = None, sort: str = "newest"):
    repo = _repo(session, owner); workbook = Workbook(write_only=True); sheet = workbook.create_sheet("Social Inventory"); sheet.append(HEADERS)
    for item in _all_filtered(repo, platform, source_id, content_type, keyword, date_from, date_to, min_engagement, sort): sheet.append([_safe(v) for v in _row(item)])
    buffer = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024); workbook.save(buffer); buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{_filename(platform, "xlsx")}"'})


@router.post("/research")
def research(data: ResearchRequest, session: DatabaseSession, owner: Owner):
    repo = _repo(session, owner); source = _source_or_404(repo, data.source_uuid)
    return asyncio.run(JevSocialProvider().research(urls=[source.canonical_url], goal=data.goal, target_count=data.target_count))
