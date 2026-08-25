"""Content Master skeleton; no collection behavior is implemented here."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.core.enums import (
    AnalysisStatus,
    CollectionStatus,
    ContentType,
    Platform,
)
from backend.core.paths import paths
from backend.db.base import Base, TimestampMixin, utc_now
from backend.db.models.types import enum_check, enum_type

if TYPE_CHECKING:
    from backend.db.models.analysis import AnalysisRun
    from backend.db.models.creator import Creator
    from backend.db.models.platform_account import PlatformAccount


class ContentItem(TimestampMixin, Base):
    __tablename__ = "content_items"
    __table_args__ = (
        enum_check("platform", Platform, "content_platform_type"),
        enum_check("content_type", ContentType, "content_type"),
        enum_check(
            "collection_status",
            CollectionStatus,
            "collection_status_type",
        ),
        enum_check("analysis_status", AnalysisStatus, "analysis_status_type"),
        UniqueConstraint(
            "platform",
            "platform_content_id",
            name="uq_content_items_platform_content_id",
        ),
        Index("ix_content_items_creator_id", "creator_id"),
        Index("ix_content_items_platform_account_id", "platform_account_id"),
        Index("ix_content_items_published_at", "published_at"),
        Index("ix_content_items_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="SET NULL"),
    )
    platform: Mapped[Platform] = mapped_column(
        enum_type(Platform, "content_platform_type"),
        nullable=False,
    )
    platform_content_id: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[ContentType] = mapped_column(
        enum_type(ContentType, "content_type"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(1000))
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    title: Mapped[str | None] = mapped_column(String(1000))
    caption: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON)
    mentions: Mapped[list[str] | None] = mapped_column(JSON)
    language: Mapped[str | None] = mapped_column(String(100))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    aspect_ratio: Mapped[float | None] = mapped_column(Float)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000))
    media_url: Mapped[str | None] = mapped_column(String(1000))
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)
    raw_storage_path: Mapped[str | None] = mapped_column(String(1000))
    local_media_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    collection_status: Mapped[CollectionStatus] = mapped_column(
        enum_type(CollectionStatus, "collection_status_type"),
        default=CollectionStatus.PENDING,
        nullable=False,
    )
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        enum_type(AnalysisStatus, "analysis_status_type"),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )

    creator: Mapped[Creator] = relationship(back_populates="content_items")
    platform_account: Mapped[PlatformAccount | None] = relationship(
        back_populates="content_items"
    )
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("local_media_path", "raw_storage_path")
    def validate_storage_path(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return paths.validate_storage_value(value)
