"""Social Inventory persistence and durable job state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, utc_now


class SocialInventorySource(Base, TimestampMixin):
    __tablename__ = "social_inventory_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "canonical_url", name="uq_social_source_owner_url"),
        Index("ix_social_source_owner_platform", "owner_id", "platform"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(500))
    username: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runs: Mapped[list["SocialInventoryRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    items: Mapped[list["SocialInventoryItem"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SocialInventoryRun(Base, TimestampMixin):
    __tablename__ = "social_inventory_runs"
    __table_args__ = (
        Index("ix_social_run_owner_status", "owner_id", "status"),
        Index("ix_social_run_lease", "status", "next_attempt_at", "lease_expires_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("social_inventory_sources.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_run_id: Mapped[str | None] = mapped_column(String(255))
    provider_dataset_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    include_comments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_comments_per_post: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list | None] = mapped_column(JSON)
    provider_metadata: Mapped[dict | None] = mapped_column(JSON)
    provider_cost: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[SocialInventorySource] = relationship(back_populates="runs")


class SocialInventoryItem(Base, TimestampMixin):
    __tablename__ = "social_inventory_items"
    __table_args__ = (
        UniqueConstraint("source_id", "platform", "external_id", name="uq_social_item_external"),
        UniqueConstraint("source_id", "platform", "canonical_url", name="uq_social_item_url"),
        Index("ix_social_item_source_published", "source_id", "published_at"),
        Index("ix_social_item_platform_hash", "platform", "content_hash"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("social_inventory_sources.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(500))
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000))
    caption: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(30))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author: Mapped[dict | None] = mapped_column(JSON)
    media: Mapped[list | None] = mapped_column(JSON)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    hashtags: Mapped[list | None] = mapped_column(JSON)
    mentions: Mapped[list | None] = mapped_column(JSON)
    location: Mapped[dict | None] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_response: Mapped[dict | None] = mapped_column(JSON)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source: Mapped[SocialInventorySource] = relationship(back_populates="items")
    snapshots: Mapped[list["SocialInventoryMetricSnapshot"]] = relationship(cascade="all, delete-orphan")
    comments: Mapped[list["SocialInventoryComment"]] = relationship(cascade="all, delete-orphan")


class SocialInventoryMetricSnapshot(Base):
    __tablename__ = "social_inventory_metric_snapshots"
    __table_args__ = (Index("ix_social_snapshot_item_observed", "item_id", "observed_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("social_inventory_items.id", ondelete="CASCADE"), nullable=False)
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    followers: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SocialInventoryComment(Base, TimestampMixin):
    __tablename__ = "social_inventory_comments"
    __table_args__ = (
        UniqueConstraint("item_id", "platform", "external_id", name="uq_social_comment_external"),
        Index("ix_social_comment_item", "item_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("social_inventory_items.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(500))
    parent_external_id: Mapped[str | None] = mapped_column(String(500))
    author: Mapped[dict | None] = mapped_column(JSON)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    likes: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_response: Mapped[dict | None] = mapped_column(JSON)
