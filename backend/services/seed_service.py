"""Idempotent non-sensitive demo data for relationship verification."""

from sqlalchemy.orm import Session

from backend.core.enums import Platform
from backend.repositories.creator_repository import CreatorRepository
from backend.schemas.creator import CreatorCreate, PlatformAccountCreate
from backend.services.creator_service import CreatorService


DEMO_CREATORS = (
    (
        CreatorCreate(
            creator_uid="CR_900001",
            display_name="Creator A",
            country="Demo",
            primary_language="en",
            category="demo",
        ),
        (
            PlatformAccountCreate(
                platform=Platform.INSTAGRAM,
                username="creator_a_demo_ig",
            ),
            PlatformAccountCreate(
                platform=Platform.TIKTOK,
                username="creator_a_demo_tt",
            ),
        ),
    ),
    (
        CreatorCreate(
            creator_uid="CR_900002",
            display_name="Creator B",
            country="Demo",
            primary_language="en",
            category="demo",
        ),
        (
            PlatformAccountCreate(
                platform=Platform.YOUTUBE,
                username="creator_b_demo_yt",
            ),
        ),
    ),
)


def seed_demo_data(session: Session) -> tuple[int, int]:
    creators = CreatorRepository(session)
    service = CreatorService(session)
    creators_added = 0
    accounts_added = 0
    for creator_data, account_data in DEMO_CREATORS:
        creator = creators.get_by_uid(creator_data.creator_uid or "")
        if creator is None:
            creator = service.create_creator(creator_data)
            creators_added += 1
        existing_platforms = {account.platform for account in creator.accounts}
        for account in account_data:
            if account.platform not in existing_platforms:
                service.add_account(creator.id, account)
                accounts_added += 1
    return creators_added, accounts_added
