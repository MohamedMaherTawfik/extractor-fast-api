"""Local Creator Master API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.enums import Platform
from backend.db.session import get_db
from backend.schemas.creator import (
    CreatorCreate,
    CreatorResponse,
    CreatorUpdate,
    PlatformAccountCreate,
    PlatformAccountResponse,
    PlatformAccountUpdate,
)
from backend.services.creator_service import CreatorService


router = APIRouter(tags=["creators"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/creators", response_model=list[CreatorResponse])
def list_creators(
    session: DatabaseSession,
    q: str | None = None,
    platform: Platform | None = None,
    country: str | None = None,
    category: str | None = None,
    active: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return CreatorService(session).list_creators(
        search=q,
        platform=platform,
        country=country,
        category=category,
        active=active,
        offset=offset,
        limit=limit,
    )


@router.get("/creators/{creator_id}", response_model=CreatorResponse)
def get_creator(creator_id: int, session: DatabaseSession):
    return CreatorService(session).get_creator(creator_id)


@router.post(
    "/creators",
    response_model=CreatorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_creator(data: CreatorCreate, session: DatabaseSession):
    return CreatorService(session).create_creator(data)


@router.patch("/creators/{creator_id}", response_model=CreatorResponse)
def update_creator(
    creator_id: int,
    data: CreatorUpdate,
    session: DatabaseSession,
):
    return CreatorService(session).update_creator(creator_id, data)


@router.get(
    "/creators/{creator_id}/accounts",
    response_model=list[PlatformAccountResponse],
)
def list_creator_accounts(creator_id: int, session: DatabaseSession):
    return CreatorService(session).list_accounts(creator_id)


@router.post(
    "/creators/{creator_id}/accounts",
    response_model=PlatformAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_creator_account(
    creator_id: int,
    data: PlatformAccountCreate,
    session: DatabaseSession,
):
    return CreatorService(session).add_account(creator_id, data)


@router.patch(
    "/platform-accounts/{account_id}",
    response_model=PlatformAccountResponse,
)
def update_platform_account(
    account_id: int,
    data: PlatformAccountUpdate,
    session: DatabaseSession,
):
    return CreatorService(session).update_account(account_id, data)
