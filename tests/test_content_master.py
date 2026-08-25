import pytest
from sqlalchemy import select

from backend.core.enums import ContentType, Platform
from backend.db.models.content_item import ContentItem
from backend.db.session import session_scope
from backend.schemas.creator import CreatorCreate, PlatformAccountCreate
from backend.services.creator_service import CreatorService


def test_content_item_relationships() -> None:
    with session_scope() as session:
        service = CreatorService(session)
        creator = service.create_creator(
            CreatorCreate(display_name="Content Owner")
        )
        account = service.add_account(
            creator.id,
            PlatformAccountCreate(
                platform=Platform.YOUTUBE,
                username="content_owner",
            ),
        )
        content = ContentItem(
            content_uid="CNT_TEST_001",
            creator_id=creator.id,
            platform_account_id=account.id,
            platform=Platform.YOUTUBE,
            platform_content_id="demo-content-id",
            content_type=ContentType.VIDEO,
            source_url="https://www.youtube.com/watch?v=demo-content-id",
            local_media_path="data/media/demo.mp4",
        )
        session.add(content)
        session.flush()
        content_id = content.id

    with session_scope() as session:
        stored = session.scalar(
            select(ContentItem).where(ContentItem.id == content_id)
        )
        assert stored is not None
        assert stored.creator.display_name == "Content Owner"
        assert stored.platform_account.username == "content_owner"
        assert not stored.local_media_path.startswith(("/", "\\"))


def test_content_item_rejects_absolute_media_path() -> None:
    absolute_path = "C:" + "\\private\\video.mp4"
    with pytest.raises(ValueError, match="project-relative"):
        ContentItem(
            content_uid="CNT_INVALID_PATH",
            creator_id=1,
            platform=Platform.YOUTUBE,
            content_type=ContentType.VIDEO,
            local_media_path=absolute_path,
        )
