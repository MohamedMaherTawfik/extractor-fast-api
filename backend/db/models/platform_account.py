"""Platform account ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import AccessStatus, Platform
from backend.db.base import Base, TimestampMixin
from backend.db.models.types import enum_check, enum_type

if TYPE_CHECKING:
    from backend.db.models.collection_run import CollectionRun
    from backend.db.models.content_item import ContentItem
    from backend.db.models.creator import Creator


class PlatformAccount(TimestampMixin, Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        enum_check("platform", Platform, "platform_type"),
        enum_check("access_status", AccessStatus, "access_status_type"),
        UniqueConstraint(
            "platform",
            "username",
            name="uq_platform_accounts_platform_username",
        ),
        UniqueConstraint(
            "platform",
            "platform_user_id",
            name="uq_platform_accounts_platform_user_id",
        ),
        UniqueConstraint(
            "profile_url",
            name="uq_platform_accounts_profile_url",
        ),
        Index("ix_platform_accounts_creator_id", "creator_id"),
        Index("ix_platform_accounts_platform", "platform"),
        Index("ix_platform_accounts_username", "username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[Platform] = mapped_column(
        enum_type(Platform, "platform_type"),
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(String(255))
    platform_user_id: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(1000))
    display_name: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    content_count: Mapped[int | None] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_status: Mapped[AccessStatus] = mapped_column(
        enum_type(AccessStatus, "access_status_type"),
        default=AccessStatus.UNKNOWN,
        nullable=False,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_cursor: Mapped[dict | None] = mapped_column(JSON)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    creator: Mapped[Creator] = relationship(back_populates="accounts")
    content_items: Mapped[list[ContentItem]] = relationship(
        back_populates="platform_account",
        passive_deletes=True,
    )
    collection_runs: Mapped[list[CollectionRun]] = relationship(
        back_populates="platform_account",
        passive_deletes=True,
    )
