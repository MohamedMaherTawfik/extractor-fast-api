"""Creator import audit models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.core.enums import ImportStatus
from backend.core.paths import paths
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type


class CreatorImportBatch(Base):
    __tablename__ = "creator_import_batches"
    __table_args__ = (
        enum_check("status", ImportStatus, "import_status_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_file: Mapped[str] = mapped_column(String(1000), nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ImportStatus] = mapped_column(
        enum_type(ImportStatus, "import_status_type"),
        default=ImportStatus.RUNNING,
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text)

    errors: Mapped[list[CreatorImportError]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("source_file")
    def validate_source_file(self, key: str, value: str) -> str:
        return paths.validate_storage_value(value)


class CreatorImportError(Base):
    __tablename__ = "creator_import_errors"
    __table_args__ = (Index("ix_creator_import_errors_batch_id", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("creator_import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    batch: Mapped[CreatorImportBatch] = relationship(back_populates="errors")
