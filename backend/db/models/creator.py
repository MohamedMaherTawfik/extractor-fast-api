"""Creator master ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.collection_run import CollectionRun
    from backend.db.models.content_item import ContentItem
    from backend.db.models.platform_account import PlatformAccount


class Creator(TimestampMixin, Base):
    __tablename__ = "creators"
    __table_args__ = (
        Index("ix_creators_display_name", "display_name"),
        Index("ix_creators_country", "country"),
        Index("ix_creators_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    primary_language: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    possible_duplicate: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    accounts: Mapped[list[PlatformAccount]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    content_items: Mapped[list[ContentItem]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    collection_runs: Mapped[list[CollectionRun]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
