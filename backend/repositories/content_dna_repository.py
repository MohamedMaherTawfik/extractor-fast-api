"""Persistence and cohort queries for canonical Content DNA."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.db.models.content_item import ContentItem
from backend.db.models.creator import Creator
from backend.db.models.pattern_recipe import ContentDNA
from backend.schemas.pattern_recipe import PatternFilters


class ContentDNARepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, identifier: int | str) -> ContentDNA | None:
        if isinstance(identifier, int) or str(identifier).isdigit():
            predicate = ContentDNA.id == int(identifier)
        else:
            predicate = ContentDNA.dna_uid == str(identifier)
        return self._session.scalar(select(ContentDNA).where(predicate))

    def by_analysis_run(self, analysis_run_id: int) -> ContentDNA | None:
        return self._session.scalar(
            select(ContentDNA).where(ContentDNA.analysis_run_id == analysis_run_id)
        )

    def latest_for_content(self, content_id: int) -> ContentDNA | None:
        return self._session.scalar(
            select(ContentDNA)
            .where(ContentDNA.content_id == content_id)
            .order_by(ContentDNA.dna_version.desc())
        )

    def next_version(self, content_id: int) -> int:
        value = self._session.scalar(
            select(func.max(ContentDNA.dna_version)).where(ContentDNA.content_id == content_id)
        )
        return int(value or 0) + 1

    def create(self, **values) -> ContentDNA:
        dna = ContentDNA(**values)
        self._session.add(dna)
        self._session.flush()
        return dna

    def list_latest(
        self,
        filters: PatternFilters | None = None,
        *,
        content_ids: list[int] | None = None,
    ) -> list[ContentDNA]:
        latest = (
            select(ContentDNA.content_id, func.max(ContentDNA.dna_version).label("version"))
            .group_by(ContentDNA.content_id)
            .subquery()
        )
        statement: Select = (
            select(ContentDNA)
            .join(
                latest,
                (ContentDNA.content_id == latest.c.content_id)
                & (ContentDNA.dna_version == latest.c.version),
            )
            .join(ContentItem, ContentItem.id == ContentDNA.content_id)
            .join(Creator, Creator.id == ContentItem.creator_id)
        )
        if content_ids is not None:
            statement = statement.where(ContentDNA.content_id.in_(content_ids))
        if filters is not None:
            if filters.platform:
                statement = statement.where(ContentItem.platform == filters.platform)
            creator_ids = filters.creator_ids or (
                [filters.creator_id] if filters.creator_id is not None else None
            )
            if creator_ids:
                statement = statement.where(ContentItem.creator_id.in_(creator_ids))
            if filters.content_type:
                statement = statement.where(ContentDNA.content_type == filters.content_type)
            if filters.category:
                statement = statement.where(Creator.category == filters.category)
            if filters.language:
                statement = statement.where(ContentItem.language == filters.language)
            if filters.country:
                statement = statement.where(Creator.country == filters.country)
            if filters.date_from:
                statement = statement.where(ContentItem.published_at >= filters.date_from)
            if filters.date_to:
                statement = statement.where(ContentItem.published_at <= filters.date_to)
            if filters.duration_min_ms is not None:
                statement = statement.where(ContentDNA.duration_ms >= filters.duration_min_ms)
            if filters.duration_max_ms is not None:
                statement = statement.where(ContentDNA.duration_ms <= filters.duration_max_ms)
        return list(self._session.scalars(statement.order_by(ContentDNA.id)))

