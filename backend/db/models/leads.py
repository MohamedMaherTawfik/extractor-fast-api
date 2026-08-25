"""Lead/prospect business acquisition persistence plane.

These tables intentionally do not share identity or transaction keys with the
Creator, Content, Product/Sales, or Answer Bot planes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, utc_now


class LeadSource(Base, TimestampMixin):
    __tablename__ = "lead_sources"
    __table_args__ = (Index("ix_lead_sources_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bulk_support: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    query_support: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    geo_support: Mapped[str] = mapped_column(String(60), nullable=False)
    credentials_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    freshness: Mapped[str] = mapped_column(String(60), nullable=False)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_status: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_limit: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    status_detail: Mapped[str | None] = mapped_column(String(500))


class LeadRun(Base):
    __tablename__ = "lead_runs"
    __table_args__ = (
        Index("ix_lead_runs_status", "status"),
        Index("ix_lead_runs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    geography: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    segments: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    planned_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_source: Mapped[str | None] = mapped_column(String(64))
    current_governorate: Mapped[str | None] = mapped_column(String(100))
    current_category: Mapped[str | None] = mapped_column(String(100))
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    jobs: Mapped[list["LeadJob"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class LeadJob(Base):
    __tablename__ = "lead_jobs"
    __table_args__ = (
        UniqueConstraint("job_uid", name="uq_lead_jobs_uid"),
        Index("ix_lead_jobs_run_status", "run_id", "status"),
        Index("ix_lead_jobs_source", "source_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("lead_runs.id", ondelete="CASCADE"), nullable=False)
    source_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    governorate: Mapped[str | None] = mapped_column(String(100))
    tile: Mapped[dict | None] = mapped_column(JSON)
    category: Mapped[str | None] = mapped_column(String(100))
    keyword_set: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    raw_storage_path: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[LeadRun] = relationship(back_populates="jobs")


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_fit_class_score", "fit_class", "fit_score"),
        Index("ix_leads_governorate_category", "governorate", "category_id"),
        Index("ix_leads_phone", "phone_normalized"),
        Index("ix_leads_domain", "domain_normalized"),
        Index("ix_leads_name_address", "business_name_normalized", "address_normalized"),
        Index("ix_leads_chain_key", "chain_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    business_name_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    business_name_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(100))
    segment_tier: Mapped[int | None] = mapped_column(Integer)
    buyer_type: Mapped[str | None] = mapped_column(String(80))
    governorate: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str | None] = mapped_column(String(160))
    address_raw: Mapped[str | None] = mapped_column(String(1000))
    address_normalized: Mapped[str | None] = mapped_column(String(1000))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    phone_raw: Mapped[str | None] = mapped_column(String(160))
    phone_normalized: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(2000))
    domain_normalized: Mapped[str | None] = mapped_column(String(255))
    social_links: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_status: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(300), nullable=False)
    source_first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_confidence: Mapped[float | None] = mapped_column(Float)
    fit_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    fit_class: Mapped[str] = mapped_column(String(4), default="C", nullable=False)
    score_explanation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    lead_status: Mapped[str] = mapped_column(String(40), default="DISCOVERED", nullable=False)
    dedupe_status: Mapped[str] = mapped_column(String(40), default="UNIQUE", nullable=False)
    master_lead_uid: Mapped[str | None] = mapped_column(String(64))
    chain_key: Mapped[str | None] = mapped_column(String(500))
    parent_business_uid: Mapped[str | None] = mapped_column(String(64))
    provenance: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    source_records: Mapped[list["LeadSourceRecord"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    dedupe_events: Mapped[list["LeadDedupeEvent"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class LeadSourceRecord(Base):
    __tablename__ = "lead_source_records"
    __table_args__ = (
        UniqueConstraint("source_uid", "source_record_id", name="uq_lead_source_record"),
        Index("ix_lead_source_records_lead", "lead_id"),
        Index("ix_lead_source_records_run", "run_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    source_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(300), nullable=False)
    collector: Mapped[str] = mapped_column(String(120), nullable=False)
    collector_version: Mapped[str] = mapped_column(String(30), nullable=False)
    acquisition_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100))
    keyword: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(100))
    governorate: Mapped[str | None] = mapped_column(String(100))
    tile: Mapped[dict | None] = mapped_column(JSON)
    run_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_storage_path: Mapped[str | None] = mapped_column(String(500))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="source_records")


class LeadDedupeEvent(Base):
    __tablename__ = "lead_dedupe_events"
    __table_args__ = (Index("ix_lead_dedupe_events_lead", "lead_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    incoming_source_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    incoming_source_record_id: Mapped[str] = mapped_column(String(300), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_signals: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    branch_decision: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="dedupe_events")


class LeadControlImport(Base):
    __tablename__ = "lead_control_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    sheet_counts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OptInLead(Base, TimestampMixin):
    """Separate consent-bearing B2C domain; never populated by POI collection."""

    __tablename__ = "opt_in_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opt_in_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(320), nullable=False)
    consent_purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    consent_source: Mapped[str] = mapped_column(String(160), nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

