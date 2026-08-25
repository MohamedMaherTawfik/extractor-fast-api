"""Content DNA, pattern-mining, performance, and recipe persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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

from backend.core.enums import (
    EvidenceType,
    PatternStability,
    PatternStatus,
    PatternType,
    RecipeCreatedBy,
    RecipeStatus,
    RecipeType,
    TrafficType,
)
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type


class ContentDNA(Base):
    __tablename__ = "content_dna"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", name="uq_content_dna_analysis_run"),
        UniqueConstraint("content_id", "dna_version", name="uq_content_dna_version"),
        Index("ix_content_dna_content_id", "content_id"),
        Index("ix_content_dna_content_type", "content_type"),
        Index("ix_content_dna_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dna_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    dna_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    identity: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    structure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visual: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    copy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    audio: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    editing: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    product: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    behavioral: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    seo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    performance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    segment_sequence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    feature_vector: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    pattern_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"
    __table_args__ = (
        enum_check("traffic_type", TrafficType, "performance_traffic_type"),
        UniqueConstraint("content_id", "metric_name", "collected_at", name="uq_performance_snapshot"),
        Index("ix_performance_snapshots_content_id", "content_id"),
        Index("ix_performance_snapshots_metric", "metric_name"),
        Index("ix_performance_snapshots_collected", "collected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[float | None] = mapped_column(Float)
    normalized_value: Mapped[float | None] = mapped_column(Float)
    availability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    elapsed_minutes: Mapped[int | None] = mapped_column(Integer)
    traffic_type: Mapped[TrafficType] = mapped_column(
        enum_type(TrafficType, "performance_traffic_type"), nullable=False
    )
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PatternMiningRun(Base):
    __tablename__ = "pattern_mining_runs"
    __table_args__ = (Index("ix_pattern_mining_runs_started", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contents_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    patterns_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    patterns_rejected_low_support: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)


class Pattern(Base):
    __tablename__ = "patterns"
    __table_args__ = (
        enum_check("pattern_type", PatternType, "pattern_type"),
        enum_check("evidence_type", EvidenceType, "pattern_evidence_type"),
        enum_check("status", PatternStatus, "pattern_status"),
        enum_check("stability", PatternStability, "pattern_stability"),
        UniqueConstraint("fingerprint", name="uq_patterns_fingerprint"),
        Index("ix_patterns_type", "pattern_type"),
        Index("ix_patterns_score", "pattern_score"),
        Index("ix_patterns_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mining_run_id: Mapped[int | None] = mapped_column(ForeignKey("pattern_mining_runs.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_type: Mapped[PatternType] = mapped_column(enum_type(PatternType, "pattern_type"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    feature_definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    support_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    performance_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_type: Mapped[EvidenceType] = mapped_column(enum_type(EvidenceType, "pattern_evidence_type"), nullable=False)
    support_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    performance_score: Mapped[float] = mapped_column(Float, nullable=False)
    consistency_score: Mapped[float] = mapped_column(Float, nullable=False)
    recency_score: Mapped[float] = mapped_column(Float, nullable=False)
    pattern_score: Mapped[float] = mapped_column(Float, nullable=False)
    stability: Mapped[PatternStability] = mapped_column(enum_type(PatternStability, "pattern_stability"), nullable=False)
    status: Mapped[PatternStatus] = mapped_column(enum_type(PatternStatus, "pattern_status"), nullable=False)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_version: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    pattern_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    features: Mapped[list[PatternFeature]] = relationship(back_populates="pattern", cascade="all, delete-orphan")
    content_links: Mapped[list[PatternContentLink]] = relationship(back_populates="pattern", cascade="all, delete-orphan")


class PatternFeature(Base):
    __tablename__ = "pattern_features"
    __table_args__ = (Index("ix_pattern_features_pattern", "pattern_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_id: Mapped[int] = mapped_column(ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(150), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    modality: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    pattern: Mapped[Pattern] = relationship(back_populates="features")


class PatternContentLink(Base):
    __tablename__ = "pattern_content_links"
    __table_args__ = (
        UniqueConstraint("pattern_id", "content_id", name="uq_pattern_content_link"),
        Index("ix_pattern_content_links_content", "content_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_id: Mapped[int] = mapped_column(ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    dna_id: Mapped[int] = mapped_column(ForeignKey("content_dna.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id", ondelete="SET NULL"))
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("content_shots.id", ondelete="SET NULL"))
    analysis_result_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_results.id", ondelete="SET NULL"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    pattern: Mapped[Pattern] = relationship(back_populates="content_links")


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        enum_check("recipe_type", RecipeType, "recipe_type"),
        enum_check("status", RecipeStatus, "recipe_status"),
        Index("ix_recipes_type", "recipe_type"),
        Index("ix_recipes_target", "target_platform", "content_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipe_type: Mapped[RecipeType] = mapped_column(enum_type(RecipeType, "recipe_type"), nullable=False)
    status: Mapped[RecipeStatus] = mapped_column(enum_type(RecipeStatus, "recipe_status"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_platform: Mapped[str | None] = mapped_column(String(50))
    target_duration_ms: Mapped[int | None] = mapped_column(Integer)
    target_category: Mapped[str | None] = mapped_column(String(150))
    language: Mapped[str | None] = mapped_column(String(100))
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recipe_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    versions: Mapped[list[RecipeVersion]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    variants: Mapped[list[RecipeVariant]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        foreign_keys="RecipeVariant.recipe_id",
    )


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"
    __table_args__ = (
        enum_check("evidence_type", EvidenceType, "recipe_evidence_type"),
        enum_check("created_by", RecipeCreatedBy, "recipe_created_by"),
        UniqueConstraint("recipe_id", "version", name="uq_recipe_version"),
        Index("ix_recipe_versions_recipe", "recipe_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_type: Mapped[EvidenceType] = mapped_column(enum_type(EvidenceType, "recipe_evidence_type"), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[RecipeCreatedBy] = mapped_column(enum_type(RecipeCreatedBy, "recipe_created_by"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="versions")
    pattern_links: Mapped[list[RecipePatternLink]] = relationship(back_populates="recipe_version", cascade="all, delete-orphan")
    content_sources: Mapped[list[RecipeContentSource]] = relationship(back_populates="recipe_version", cascade="all, delete-orphan")


class RecipePatternLink(Base):
    __tablename__ = "recipe_pattern_links"
    __table_args__ = (UniqueConstraint("recipe_version_id", "pattern_id", name="uq_recipe_pattern_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_version_id: Mapped[int] = mapped_column(ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False)
    pattern_id: Mapped[int] = mapped_column(ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    recipe_version: Mapped[RecipeVersion] = relationship(back_populates="pattern_links")


class RecipeContentSource(Base):
    __tablename__ = "recipe_content_sources"
    __table_args__ = (UniqueConstraint("recipe_version_id", "content_id", name="uq_recipe_content_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_version_id: Mapped[int] = mapped_column(ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    recipe_version: Mapped[RecipeVersion] = relationship(back_populates="content_sources")


class RecipeVariant(Base):
    __tablename__ = "recipe_variants"
    __table_args__ = (Index("ix_recipe_variants_recipe", "recipe_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    base_version_id: Mapped[int] = mapped_column(ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_variables: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    experiment_id: Mapped[str | None] = mapped_column(String(100))
    control_recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(50), default="experimental", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    recipe: Mapped[Recipe] = relationship(back_populates="variants", foreign_keys=[recipe_id])
