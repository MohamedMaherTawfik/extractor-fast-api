"""Owner-scoped persistence, filtering, leasing, and idempotent upserts."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from backend.db.models.social_inventory import SocialInventoryComment, SocialInventoryItem, SocialInventoryMetricSnapshot, SocialInventoryRun, SocialInventorySource
from backend.social_inventory.normalizer import content_hash
from backend.social_inventory.schemas import NormalizedSocialItem


class SocialInventoryRepository:
    def __init__(self, session: Session, owner_id: str) -> None:
        self.session = session
        self.owner_id = owner_id

    def list_sources(self) -> list[SocialInventorySource]:
        return list(self.session.scalars(select(SocialInventorySource).where(SocialInventorySource.owner_id == self.owner_id).order_by(SocialInventorySource.created_at.desc())))

    def enqueue_due_syncs(self) -> int:
        now = datetime.now(UTC); created = 0
        due = self.session.scalars(select(SocialInventorySource).where(SocialInventorySource.owner_id == self.owner_id, SocialInventorySource.sync_enabled.is_(True), SocialInventorySource.next_sync_at.is_not(None), SocialInventorySource.next_sync_at <= now)).all()
        for source in due:
            active = self.session.scalar(select(func.count()).select_from(SocialInventoryRun).where(SocialInventoryRun.source_id == source.id, SocialInventoryRun.status.in_(["queued", "starting", "running", "importing"])))
            if active: continue
            settings = source.settings or {}
            self.create_run(source, provider=source.provider, status="queued", request_id=str(uuid4()), max_items=int(settings.get("max_items") or 100), include_comments=bool(settings.get("include_comments")), max_comments_per_post=int(settings.get("max_comments_per_post") or 0), date_from=datetime.fromisoformat(settings["date_from"]) if settings.get("date_from") else None, date_to=datetime.fromisoformat(settings["date_to"]) if settings.get("date_to") else None)
            source.next_sync_at = now + timedelta(minutes=source.sync_interval_minutes or 60); created += 1
        return created

    def get_source(self, source_uuid: UUID) -> SocialInventorySource | None:
        return self.session.scalar(select(SocialInventorySource).where(SocialInventorySource.uuid == source_uuid, SocialInventorySource.owner_id == self.owner_id))

    def get_or_create_source(self, **values) -> SocialInventorySource:
        item = self.session.scalar(select(SocialInventorySource).where(SocialInventorySource.owner_id == self.owner_id, SocialInventorySource.canonical_url == values["canonical_url"]))
        if item is None:
            item = SocialInventorySource(owner_id=self.owner_id, **values)
            self.session.add(item)
            self.session.flush()
        return item

    def create_run(self, source: SocialInventorySource, **values) -> SocialInventoryRun:
        item = SocialInventoryRun(source_id=source.id, owner_id=self.owner_id, **values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_run(self, run_uuid: UUID) -> SocialInventoryRun | None:
        return self.session.scalar(select(SocialInventoryRun).where(SocialInventoryRun.uuid == run_uuid, SocialInventoryRun.owner_id == self.owner_id))

    def list_runs(self, offset: int, limit: int) -> list[SocialInventoryRun]:
        return list(self.session.scalars(select(SocialInventoryRun).where(SocialInventoryRun.owner_id == self.owner_id).order_by(SocialInventoryRun.created_at.desc()).offset(offset).limit(limit)))

    def claim_run(self, worker_id: str, lease_seconds: int = 60) -> SocialInventoryRun | None:
        now = datetime.now(UTC)
        candidate = self.session.scalar(select(SocialInventoryRun.id).where(
            SocialInventoryRun.status.in_(["queued", "starting", "running", "importing"]),
            or_(SocialInventoryRun.next_attempt_at.is_(None), SocialInventoryRun.next_attempt_at <= now),
            or_(SocialInventoryRun.lease_expires_at.is_(None), SocialInventoryRun.lease_expires_at < now),
        ).order_by(SocialInventoryRun.created_at).limit(1))
        if candidate is None:
            return None
        changed = self.session.execute(update(SocialInventoryRun).where(SocialInventoryRun.id == candidate, or_(SocialInventoryRun.lease_expires_at.is_(None), SocialInventoryRun.lease_expires_at < now)).values(lease_owner=worker_id, lease_expires_at=now + timedelta(seconds=lease_seconds))).rowcount
        self.session.flush()
        return self.session.get(SocialInventoryRun, candidate) if changed else None

    def release(self, run: SocialInventoryRun, delay_seconds: int = 0) -> None:
        run.lease_owner = None
        run.lease_expires_at = None
        run.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds) if delay_seconds else None

    def list_items(self, *, offset: int, limit: int, platform: str | None = None, source_id: int | None = None, content_type: str | None = None, keyword: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, min_engagement: int | None = None, sort: str = "newest") -> tuple[list[SocialInventoryItem], int]:
        statement = select(SocialInventoryItem).join(SocialInventorySource).where(SocialInventorySource.owner_id == self.owner_id)
        count = select(func.count()).select_from(SocialInventoryItem).join(SocialInventorySource).where(SocialInventorySource.owner_id == self.owner_id)
        filters = []
        if platform: filters.append(SocialInventoryItem.platform == platform)
        if source_id: filters.append(SocialInventoryItem.source_id == source_id)
        if content_type: filters.append(SocialInventoryItem.content_type == content_type)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(or_(SocialInventoryItem.caption.ilike(pattern), SocialInventoryItem.title.ilike(pattern)))
        if date_from: filters.append(SocialInventoryItem.published_at >= date_from)
        if date_to: filters.append(SocialInventoryItem.published_at <= date_to)
        if min_engagement is not None:
            filters.append((func.coalesce(func.json_extract(SocialInventoryItem.metrics, "$.likes"), 0) + func.coalesce(func.json_extract(SocialInventoryItem.metrics, "$.comments"), 0) + func.coalesce(func.json_extract(SocialInventoryItem.metrics, "$.shares"), 0)) >= min_engagement)
        if filters:
            statement = statement.where(*filters); count = count.where(*filters)
        sort_column = {"oldest": SocialInventoryItem.published_at.asc(), "most_viewed": func.json_extract(SocialInventoryItem.metrics, "$.views").desc(), "most_liked": func.json_extract(SocialInventoryItem.metrics, "$.likes").desc(), "most_commented": func.json_extract(SocialInventoryItem.metrics, "$.comments").desc()}.get(sort, SocialInventoryItem.published_at.desc())
        return list(self.session.scalars(statement.order_by(sort_column, SocialInventoryItem.id.desc()).offset(offset).limit(limit))), int(self.session.scalar(count) or 0)

    def get_item(self, item_uuid: UUID) -> SocialInventoryItem | None:
        return self.session.scalar(select(SocialInventoryItem).join(SocialInventorySource).where(SocialInventoryItem.uuid == item_uuid, SocialInventorySource.owner_id == self.owner_id))

    def upsert_item(self, source_id: int, normalized: NormalizedSocialItem) -> tuple[SocialInventoryItem, bool, bool, int]:
        digest = content_hash(normalized)
        filters = []
        if normalized.external_id:
            filters.append(and_(SocialInventoryItem.platform == normalized.platform, SocialInventoryItem.external_id == normalized.external_id))
        filters.append(and_(SocialInventoryItem.platform == normalized.platform, SocialInventoryItem.canonical_url == normalized.canonical_url))
        filters.append(and_(SocialInventoryItem.platform == normalized.platform, SocialInventoryItem.content_hash == digest))
        item = self.session.scalar(select(SocialInventoryItem).where(SocialInventoryItem.source_id == source_id, or_(*filters)))
        metrics = normalized.metrics.model_dump()
        created = item is None
        snapshot = False
        if created:
            item = SocialInventoryItem(source_id=source_id, platform=normalized.platform, external_id=normalized.external_id, canonical_url=normalized.canonical_url, content_hash=digest, content_type=normalized.content_type, first_observed_at=normalized.observed_at)
            self.session.add(item)
        elif (item.metrics or {}) != metrics:
            snapshot = True
        for key in ("title", "caption", "language", "published_at", "location", "provider"):
            setattr(item, key, getattr(normalized, key))
        item.author = normalized.author.model_dump(); item.media = [value.model_dump() for value in normalized.media]
        item.metrics = metrics; item.hashtags = normalized.hashtags; item.mentions = normalized.mentions
        item.provider_response = normalized.provider_response; item.last_observed_at = normalized.observed_at
        self.session.flush()
        if created or snapshot:
            self.session.add(SocialInventoryMetricSnapshot(item_id=item.id, **metrics, followers=normalized.author.followers_count, observed_at=normalized.observed_at))
        comments_created = 0
        for raw in normalized.comments:
            external_id = raw.get("id") or raw.get("commentId")
            existing = self.session.scalar(select(SocialInventoryComment).where(SocialInventoryComment.item_id == item.id, SocialInventoryComment.platform == normalized.platform, SocialInventoryComment.external_id == str(external_id))) if external_id else None
            if existing is None and (raw.get("text") or raw.get("body")):
                self.session.add(SocialInventoryComment(item_id=item.id, platform=normalized.platform, external_id=str(external_id) if external_id else None, parent_external_id=raw.get("parentId"), author=raw.get("author") if isinstance(raw.get("author"), dict) else None, body=str(raw.get("text") or raw.get("body")), likes=raw.get("likes"), provider_response=raw))
                comments_created += 1
        self.session.flush()
        return item, created, not created, comments_created

    def overview(self) -> dict[str, Any]:
        sources = select(SocialInventorySource.id).where(SocialInventorySource.owner_id == self.owner_id)
        items = select(SocialInventoryItem).where(SocialInventoryItem.source_id.in_(sources)).subquery()
        last_sync = self.session.scalar(select(func.max(SocialInventorySource.last_synced_at)).where(SocialInventorySource.owner_id == self.owner_id))
        failed = self.session.scalar(select(func.count()).select_from(SocialInventoryRun).where(SocialInventoryRun.owner_id == self.owner_id, SocialInventoryRun.status.in_(["failed", "partial"]))) or 0
        return {"sources": len(self.list_sources()), "items": int(self.session.scalar(select(func.count()).select_from(items)) or 0), "total_views": int(self.session.scalar(select(func.coalesce(func.sum(func.json_extract(items.c.metrics, "$.views")), 0))) or 0), "total_engagement": int(self.session.scalar(select(func.coalesce(func.sum(func.coalesce(func.json_extract(items.c.metrics, "$.likes"), 0) + func.coalesce(func.json_extract(items.c.metrics, "$.comments"), 0) + func.coalesce(func.json_extract(items.c.metrics, "$.shares"), 0)), 0))) or 0), "last_sync": last_sync, "problem_runs": int(failed)}
