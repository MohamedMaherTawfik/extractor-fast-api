"""Social Inventory business service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.db.models.social_inventory import SocialInventoryRun, SocialInventorySource
from backend.social_inventory.exceptions import SocialInventoryError, feature_disabled
from backend.social_inventory.repository import SocialInventoryRepository
from backend.social_inventory.schemas import SourceCreate, SourceUpdate
from backend.social_inventory.url_validation import validate_social_url


class SocialInventoryService:
    def __init__(self, session: Session, owner_id: str = "local-operator", settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.repo = SocialInventoryRepository(session, owner_id)

    def ensure_enabled(self) -> None:
        if not self.settings.social_inventory_enabled:
            raise feature_disabled()

    def create_source_and_run(self, data: SourceCreate, request_id: str | None = None) -> tuple[SocialInventorySource, SocialInventoryRun]:
        self.ensure_enabled()
        canonical, detected = validate_social_url(data.source_url)
        platform = data.platform or detected
        if data.platform and data.platform != detected:
            raise SocialInventoryError("SOCIAL_PLATFORM_NOT_SUPPORTED", "Selected platform does not match the URL.", status_code=422)
        if data.max_items > self.settings.social_inventory_max_items:
            raise SocialInventoryError("SOCIAL_RESULT_TOO_LARGE", f"max_items cannot exceed {self.settings.social_inventory_max_items}.", status_code=422)
        if data.max_comments_per_post > self.settings.social_inventory_max_comments_per_post:
            raise SocialInventoryError("SOCIAL_RESULT_TOO_LARGE", f"max_comments_per_post cannot exceed {self.settings.social_inventory_max_comments_per_post}.", status_code=422)
        if not getattr(self.settings, f"apify_{platform}_actor_id", None):
            raise SocialInventoryError("SOCIAL_PLATFORM_NOT_CONFIGURED", f"No Apify actor is configured for {platform}.", status_code=422)
        source = self.repo.get_or_create_source(provider=data.provider, platform=platform, source_url=data.source_url, canonical_url=canonical, settings={"max_items": data.max_items, "date_from": data.date_from.isoformat() if data.date_from else None, "date_to": data.date_to.isoformat() if data.date_to else None, "include_comments": data.include_comments, "max_comments_per_post": data.max_comments_per_post})
        run = self.repo.create_run(source, provider=data.provider, status="queued", request_id=request_id or str(uuid4()), max_items=data.max_items, include_comments=data.include_comments, max_comments_per_post=data.max_comments_per_post, date_from=data.date_from, date_to=data.date_to)
        return source, run

    def sync(self, source: SocialInventorySource, request_id: str | None = None) -> SocialInventoryRun:
        settings = source.settings or {}
        return self.repo.create_run(source, provider=source.provider, status="queued", request_id=request_id or str(uuid4()), max_items=min(int(settings.get("max_items") or 100), self.settings.social_inventory_max_items), include_comments=bool(settings.get("include_comments")), max_comments_per_post=min(int(settings.get("max_comments_per_post") or 0), self.settings.social_inventory_max_comments_per_post), date_from=_parse(settings.get("date_from")), date_to=_parse(settings.get("date_to")))

    def update_source(self, source: SocialInventorySource, data: SourceUpdate) -> SocialInventorySource:
        values = data.model_dump(exclude_unset=True)
        for key, value in values.items(): setattr(source, key, value)
        if source.sync_enabled and source.sync_interval_minutes:
            source.next_sync_at = datetime.now(UTC) + timedelta(minutes=source.sync_interval_minutes)
        elif not source.sync_enabled:
            source.next_sync_at = None
        self.repo.session.flush()
        return source

    def cancel(self, run: SocialInventoryRun) -> SocialInventoryRun:
        if run.status not in {"succeeded", "partial", "failed", "cancelled"}:
            run.status = "cancelled"; run.finished_at = datetime.now(UTC); self.repo.release(run)
        return run

    def retry(self, run: SocialInventoryRun) -> SocialInventoryRun:
        if run.status not in {"failed", "partial", "cancelled"}:
            raise SocialInventoryError("SOCIAL_PROVIDER_FAILED", "Only terminal unsuccessful runs can be retried.", status_code=409)
        run.status = "queued"; run.error_code = None; run.error_message = None; run.finished_at = None; run.next_attempt_at = None; run.lease_owner = None; run.lease_expires_at = None
        return run


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
