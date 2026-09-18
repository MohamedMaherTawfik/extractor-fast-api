"""Creator Discovery Studio persistence, isolated from lead acquisition."""

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


class CreatorDiscoveryRun(Base):
    __tablename__ = "creator_discovery_runs"
    __table_args__ = (
        Index("ix_creator_discovery_runs_status", "status"),
        Index("ix_creator_discovery_runs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False)
    platforms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    options: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    jobs: Mapped[list["CreatorDiscoveryJob"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    @property
    def progress_percent(self) -> float:
        if not self.jobs:
            return 0.0
        values = [float((job.checkpoint or {}).get("progress_percent") or 0) for job in self.jobs]
        return round(sum(values) / len(values), 2)

    @property
    def stage(self) -> str:
        active = next((job for job in self.jobs if job.status == "RUNNING"), None)
        if active is not None:
            return active.stage
        return self.status


class CreatorDiscoveryJob(Base):
    __tablename__ = "creator_discovery_jobs"
    __table_args__ = (
        Index("ix_creator_discovery_jobs_run_status", "run_id", "status"),
        UniqueConstraint("job_uid", name="uq_creator_discovery_jobs_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("creator_discovery_runs.id", ondelete="CASCADE"), nullable=False
    )
    input_value: Mapped[str] = mapped_column(String(2000), nullable=False)
    normalized_input: Mapped[str] = mapped_column(String(1000), nullable=False)
    input_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    platforms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[CreatorDiscoveryRun] = relationship(back_populates="jobs")
    candidates: Mapped[list["CreatorCandidate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def stage(self) -> str:
        return str((self.checkpoint or {}).get("stage") or self.status)

    @property
    def progress_percent(self) -> float:
        return float((self.checkpoint or {}).get("progress_percent") or 0)


class CreatorCandidate(Base, TimestampMixin):
    __tablename__ = "creator_candidates"
    __table_args__ = (
        Index("ix_creator_candidates_review", "review_status", "confidence"),
        Index("ix_creator_candidates_run_platform", "run_id", "platform"),
        UniqueConstraint("candidate_uid", name="uq_creator_candidates_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("creator_discovery_runs.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("creator_discovery_jobs.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("creators.id", ondelete="SET NULL"))
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    normalized_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    public_bio: Mapped[str | None] = mapped_column(Text)
    public_avatar_url: Mapped[str | None] = mapped_column(String(2000))
    followers: Mapped[int | None] = mapped_column(Integer)
    following: Mapped[int | None] = mapped_column(Integer)
    content_count: Mapped[int | None] = mapped_column(Integer)
    verified: Mapped[bool | None] = mapped_column(Boolean)
    discovery_source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    identity_status: Mapped[str] = mapped_column(String(40), default="IDENTITY_RESOLVED", nullable=False)
    data_collection_status: Mapped[str] = mapped_column(String(50), default="DATA_COLLECTION_REQUIRED", nullable=False)
    data_completeness: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    connector_requirement: Mapped[str] = mapped_column(String(50), default="API_REQUIRED", nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job: Mapped[CreatorDiscoveryJob] = relationship(back_populates="candidates")
    match_evidence: Mapped[list["CreatorMatchEvidence"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class CreatorDiscoveryProfile(Base, TimestampMixin):
    __tablename__ = "creator_profiles"
    __table_args__ = (
        UniqueConstraint("creator_id", name="uq_creator_profiles_creator"),
        Index("ix_creator_profiles_industry", "industry"),
        Index("ix_creator_profiles_main_platform", "main_platform"),
        Index("ix_creator_profiles_match", "match_confidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), default="UNKNOWN", nullable=False)
    industry: Mapped[str] = mapped_column(String(120), default="UNKNOWN", nullable=False)
    main_platform: Mapped[str] = mapped_column(String(30), default="UNKNOWN", nullable=False)
    main_platform_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    youtube_url: Mapped[str | None] = mapped_column(String(2000))
    facebook_url: Mapped[str | None] = mapped_column(String(2000))
    instagram_url: Mapped[str | None] = mapped_column(String(2000))
    tiktok_url: Mapped[str | None] = mapped_column(String(2000))
    snapchat_url: Mapped[str | None] = mapped_column(String(2000))
    linkedin_url: Mapped[str | None] = mapped_column(String(2000))
    x_url: Mapped[str | None] = mapped_column(String(2000))
    content_mechanism_style: Mapped[str] = mapped_column(String(1000), default="UNKNOWN", nullable=False)
    influence_size: Mapped[str] = mapped_column(String(100), default="UNKNOWN", nullable=False)
    influence_size_numeric: Mapped[int | None] = mapped_column(Integer)
    kpi_impact: Mapped[str] = mapped_column(String(500), default="UNKNOWN", nullable=False)
    start_year: Mapped[int | None] = mapped_column(Integer)
    start_year_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    start_year_source: Mapped[str | None] = mapped_column(String(2000))
    match_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    identity_status: Mapped[str] = mapped_column(String(40), default="IDENTITY_RESOLVED", nullable=False)
    data_collection_status: Mapped[str] = mapped_column(String(50), default="DATA_COLLECTION_REQUIRED", nullable=False)
    data_completeness: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    connector_requirement: Mapped[str] = mapped_column(String(50), default="API_REQUIRED", nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(40), default="COLLECTION_PENDING", nullable=False)
    provenance: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class CreatorDiscoveryAccount(Base):
    __tablename__ = "creator_discovery_accounts"
    __table_args__ = (
        Index("ix_creator_discovery_accounts_creator", "creator_id"),
        Index("ix_creator_discovery_accounts_platform", "platform"),
        UniqueConstraint("platform", "profile_url", name="uq_creator_discovery_account_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    followers: Mapped[int | None] = mapped_column(Integer)
    following: Mapped[int | None] = mapped_column(Integer)
    content_count: Mapped[int | None] = mapped_column(Integer)
    bio: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    identity_status: Mapped[str] = mapped_column(String(40), default="IDENTITY_RESOLVED", nullable=False)
    data_collection_status: Mapped[str] = mapped_column(String(50), default="DATA_COLLECTION_REQUIRED", nullable=False)
    data_completeness: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    connector_requirement: Mapped[str] = mapped_column(String(50), default="API_REQUIRED", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class CreatorContentSample(Base):
    __tablename__ = "creator_content_samples"
    __table_args__ = (
        Index("ix_creator_content_samples_creator", "creator_id"),
        UniqueConstraint("platform", "content_url", name="uq_creator_content_sample_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("creator_discovery_accounts.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    content_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    platform_content_id: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str | None] = mapped_column(String(1000))
    caption: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    hashtags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    provenance: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CreatorDiscoveryAnalysis(Base):
    __tablename__ = "creator_analysis"
    __table_args__ = (Index("ix_creator_analysis_profile", "profile_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_references: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CreatorMatchEvidence(Base):
    __tablename__ = "creator_match_evidence"
    __table_args__ = (Index("ix_creator_match_evidence_candidate", "candidate_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("creator_candidates.id", ondelete="CASCADE"), nullable=False
    )
    signal: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    candidate: Mapped[CreatorCandidate] = relationship(back_populates="match_evidence")


class CreatorSource(Base):
    __tablename__ = "creator_sources"
    __table_args__ = (Index("ix_creator_sources_profile_field", "profile_id", "field_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CreatorIndustry(Base, TimestampMixin):
    __tablename__ = "creator_industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
