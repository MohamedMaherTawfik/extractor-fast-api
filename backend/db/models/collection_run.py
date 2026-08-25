"""Persistent collection job state, suitable for later worker execution."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import CollectionRunStatus
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type

if TYPE_CHECKING:
    from backend.db.models.creator import Creator
    from backend.db.models.platform_account import PlatformAccount


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        enum_check("status", CollectionRunStatus, "collection_run_status_type"),
        Index("ix_collection_runs_creator_id", "creator_id"),
        Index("ix_collection_runs_platform_account_id", "platform_account_id"),
        Index("ix_collection_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creator_id: Mapped[int | None] = mapped_column(
        ForeignKey("creators.id", ondelete="CASCADE")
    )
    platform_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="SET NULL")
    )
    connector: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[CollectionRunStatus] = mapped_column(
        enum_type(CollectionRunStatus, "collection_run_status_type"),
        default=CollectionRunStatus.QUEUED,
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(2000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cursor_state: Mapped[dict | None] = mapped_column(JSON)
    options: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    errors: Mapped[list[dict] | None] = mapped_column(JSON)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    creator: Mapped[Creator | None] = relationship(back_populates="collection_runs")
    platform_account: Mapped[PlatformAccount | None] = relationship(
        back_populates="collection_runs"
    )
