"""Persistent multimodal generation jobs, assets, prompts, QA, and provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import (
    GeneratedAssetStatus, GenerationJobStatus, GenerationPriority, GenerationRetryType,
    GenerationType, ProviderAvailability, ProviderLocality, QACategory, QAResultStatus,
    ReferenceRole, ReproducibilityLevel,
)
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"
    __table_args__ = (
        enum_check("locality", ProviderLocality, "provider_locality"),
        enum_check("availability", ProviderAvailability, "provider_availability"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    locality: Mapped[ProviderLocality] = mapped_column(enum_type(ProviderLocality, "provider_locality"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    availability: Mapped[ProviderAvailability] = mapped_column(enum_type(ProviderAvailability, "provider_availability"), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        enum_check("locality", ProviderLocality, "model_locality"),
        enum_check("availability", ProviderAvailability, "model_availability"),
        UniqueConstraint("provider_code", "model_id", "model_version", name="uq_model_profile"),
        Index("ix_model_profiles_available", "enabled", "availability"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    locality: Mapped[ProviderLocality] = mapped_column(enum_type(ProviderLocality, "model_locality"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    availability: Mapped[ProviderAvailability] = mapped_column(enum_type(ProviderAvailability, "model_availability"), nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    privacy_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_score: Mapped[float] = mapped_column(Float, nullable=False)
    latency_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_class: Mapped[str] = mapped_column(String(50), nullable=False)
    license_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        enum_check("status", GenerationJobStatus, "generation_job_status"),
        enum_check("generation_type", GenerationType, "generation_type"),
        enum_check("priority", GenerationPriority, "generation_priority"),
        Index("ix_generation_jobs_status_priority", "status", "priority"),
        Index("ix_generation_jobs_cache", "idempotency_key", "status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(100))
    generation_contract_id: Mapped[int] = mapped_column(ForeignKey("generation_contracts.id", ondelete="RESTRICT"), nullable=False)
    generation_contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)
    generation_type: Mapped[GenerationType] = mapped_column(enum_type(GenerationType, "generation_type"), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    model_id: Mapped[str | None] = mapped_column(String(255))
    model_version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[GenerationJobStatus] = mapped_column(enum_type(GenerationJobStatus, "generation_job_status"), nullable=False)
    priority: Mapped[GenerationPriority] = mapped_column(enum_type(GenerationPriority, "generation_priority"), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    max_cost: Mapped[float | None] = mapped_column(Float)
    max_duration_seconds: Mapped[float | None] = mapped_column(Float)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reproducibility_level: Mapped[ReproducibilityLevel] = mapped_column(enum_type(ReproducibilityLevel, "generation_reproducibility"), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[str | None] = mapped_column(String(255))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    assets: Mapped[list[GeneratedAsset]] = relationship(back_populates="job")
    attempts: Mapped[list[GenerationAttempt]] = relationship(back_populates="job", cascade="all, delete-orphan")
    events: Mapped[list[GenerationEvent]] = relationship(back_populates="job", cascade="all, delete-orphan")


class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"
    __table_args__ = (
        enum_check("retry_type", GenerationRetryType, "generation_retry_type"),
        UniqueConstraint("job_id", "attempt_number", name="uq_generation_attempt"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    retry_type: Mapped[GenerationRetryType] = mapped_column(enum_type(GenerationRetryType, "generation_retry_type"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    failed_checks: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    changes_applied: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_reference: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped[GenerationJob] = relationship(back_populates="attempts")


class GenerationEvent(Base):
    __tablename__ = "generation_events"
    __table_args__ = (Index("ix_generation_events_job_time", "job_id", "timestamp"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_reference: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    job: Mapped[GenerationJob] = relationship(back_populates="events")


class PromptPackage(Base):
    __tablename__ = "prompt_packages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    versions: Mapped[list[PromptPackageVersion]] = relationship(back_populates="package", cascade="all, delete-orphan")


class PromptPackageVersion(Base):
    __tablename__ = "prompt_package_versions"
    __table_args__ = (UniqueConstraint("prompt_package_id", "version", name="uq_prompt_package_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_package_id: Mapped[int] = mapped_column(ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    package: Mapped[PromptPackage] = relationship(back_populates="versions")


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"
    __table_args__ = (
        enum_check("status", GeneratedAssetStatus, "generated_asset_status"),
        Index("ix_generated_assets_job", "job_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="RESTRICT"), nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[GeneratedAssetStatus] = mapped_column(enum_type(GeneratedAssetStatus, "generated_asset_status"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    job: Mapped[GenerationJob] = relationship(back_populates="assets")
    versions: Mapped[list[AssetVersion]] = relationship(back_populates="asset", cascade="all, delete-orphan", foreign_keys="AssetVersion.asset_id")


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "version", name="uq_asset_version"),
        Index("ix_asset_versions_checksum", "checksum"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("generated_assets.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_asset_version_id: Mapped[int | None] = mapped_column(ForeignKey("asset_versions.id", ondelete="SET NULL"))
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    aspect_ratio: Mapped[str | None] = mapped_column(String(30))
    format: Mapped[str | None] = mapped_column(String(30))
    color_profile: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    qa_status: Mapped[str] = mapped_column(String(50), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    repair_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    asset: Mapped[GeneratedAsset] = relationship(back_populates="versions", foreign_keys=[asset_id])


class AssetReference(Base):
    __tablename__ = "asset_references"
    __table_args__ = (enum_check("reference_role", ReferenceRole, "reference_role"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    reference_asset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_role: Mapped[ReferenceRole] = mapped_column(enum_type(ReferenceRole, "reference_role"), nullable=False)
    rights_status: Mapped[str] = mapped_column(String(50), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


class GenerationQARun(Base):
    __tablename__ = "generation_qa_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qa_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[int] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    results: Mapped[list[GenerationQAResult]] = relationship(back_populates="run", cascade="all, delete-orphan")


class GenerationQAResult(Base):
    __tablename__ = "generation_qa_results"
    __table_args__ = (
        enum_check("category", QACategory, "generation_qa_category"),
        enum_check("result", QAResultStatus, "generation_qa_result"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("generation_qa_runs.id", ondelete="CASCADE"), nullable=False)
    check_id: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[QACategory] = mapped_column(enum_type(QACategory, "generation_qa_category"), nullable=False)
    result: Mapped[QAResultStatus] = mapped_column(enum_type(QAResultStatus, "generation_qa_result"), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str | None] = mapped_column(String(100))
    automatically_repairable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    run: Mapped[GenerationQARun] = relationship(back_populates="results")


class GenerationCostRecord(Base):
    __tablename__ = "generation_costs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("generation_attempts.id", ondelete="SET NULL"))
    provider_cost: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    input_units: Mapped[float] = mapped_column(Float, nullable=False)
    output_units: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    generation_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ContinuityState(Base):
    __tablename__ = "continuity_states"
    __table_args__ = (UniqueConstraint("job_id", "shot_id", name="uq_continuity_state"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    shot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_shot_id: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Storyboard(Base):
    __tablename__ = "storyboards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storyboard_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    shots: Mapped[list[StoryboardShot]] = relationship(back_populates="storyboard", cascade="all, delete-orphan")


class StoryboardShot(Base):
    __tablename__ = "storyboard_shots"
    __table_args__ = (UniqueConstraint("storyboard_id", "shot_id", name="uq_storyboard_shot"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False)
    shot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_id: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    storyboard: Mapped[Storyboard] = relationship(back_populates="shots")


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provenance_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    asset_version_id: Mapped[int] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False)
    contract_id: Mapped[int] = mapped_column(ForeignKey("generation_contracts.id", ondelete="RESTRICT"), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_package_version_id: Mapped[int] = mapped_column(ForeignKey("prompt_package_versions.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    reference_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    character_version: Mapped[str | None] = mapped_column(String(100))
    brand_version: Mapped[str | None] = mapped_column(String(100))
    product_version: Mapped[str | None] = mapped_column(String(100))
    transformations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    c2pa_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
