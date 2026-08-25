"""Canonical content upsert and platform-scoped deduplication."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.core.enums import CollectionStatus, Platform
from backend.db.models.content_item import ContentItem
from backend.schemas.content import NormalizedContent


UpsertOutcome = Literal["created", "updated", "skipped"]


@dataclass(frozen=True)
class ContentUpsertResult:
    item: ContentItem
    outcome: UpsertOutcome


class ContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, content_id: int) -> ContentItem | None:
        return self._session.get(ContentItem, content_id)

    def get_by_uid(self, content_uid: str) -> ContentItem | None:
        return self._session.scalar(
            select(ContentItem).where(ContentItem.content_uid == content_uid)
        )

    def list_for_account(self, account_id: int) -> list[ContentItem]:
        statement = (
            select(ContentItem)
            .where(ContentItem.platform_account_id == account_id)
            .order_by(ContentItem.published_at.desc(), ContentItem.id.desc())
        )
        return list(self._session.scalars(statement))

    def list_by_ids(self, content_ids: list[int]) -> list[ContentItem]:
        if not content_ids:
            return []
        return list(
            self._session.scalars(
                select(ContentItem).where(ContentItem.id.in_(content_ids))
            )
        )

    def upsert(
        self,
        content: NormalizedContent,
        *,
        creator_id: int,
        platform_account_id: int,
        raw_storage_path: str | None,
        local_media_path: str | None = None,
    ) -> ContentUpsertResult:
        content_hash = content.content_hash or build_content_hash(content)
        existing = self._find_existing(content, content_hash)
        values = content.model_dump(exclude={"account_identity"})
        values.update(
            creator_id=creator_id,
            platform_account_id=platform_account_id,
            raw_storage_path=raw_storage_path,
            content_hash=content_hash,
            collection_status=CollectionStatus.COLLECTED,
        )
        if local_media_path is not None:
            values["local_media_path"] = local_media_path

        if existing is None:
            item = ContentItem(**values)
            self._session.add(item)
            self._session.flush()
            return ContentUpsertResult(item, "created")

        if existing.content_hash == content_hash and local_media_path is None:
            return ContentUpsertResult(existing, "skipped")

        values.pop("content_uid", None)
        if local_media_path is None:
            values.pop("local_media_path", None)
        for field, value in values.items():
            setattr(existing, field, value)
        self._session.flush()
        return ContentUpsertResult(existing, "updated")

    def _find_existing(
        self,
        content: NormalizedContent,
        content_hash: str,
    ) -> ContentItem | None:
        if content.platform_content_id:
            statement = select(ContentItem).where(
                ContentItem.platform == content.platform,
                ContentItem.platform_content_id == content.platform_content_id,
            )
            found = self._session.scalar(statement)
            if found:
                return found

        urls = [url for url in (content.canonical_url, content.source_url) if url]
        if urls:
            statement = select(ContentItem).where(
                ContentItem.platform == content.platform,
                or_(
                    ContentItem.canonical_url.in_(urls),
                    ContentItem.source_url.in_(urls),
                ),
            )
            found = self._session.scalar(statement)
            if found:
                return found

        statement = select(ContentItem).where(
            ContentItem.platform == content.platform,
            ContentItem.content_hash == content_hash,
        )
        return self._session.scalar(statement)


def build_content_hash(content: NormalizedContent) -> str:
    values = content.model_dump(
        mode="json",
        exclude={
            "account_identity",
            "collected_at",
            "content_hash",
            "content_uid",
            "creator_id",
            "platform_account_id",
            "raw_metadata",
        },
    )
    encoded = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
