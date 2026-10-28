"""Recoverable run state machine executed by the standalone worker."""

import asyncio
from datetime import UTC, datetime
from typing import Callable

from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.db.models.social_inventory import SocialInventoryRun
from backend.social_inventory.exceptions import SocialInventoryError
from backend.social_inventory.normalizer import normalize_item
from backend.social_inventory.providers.apify import ApifyProvider
from backend.social_inventory.providers.base import SocialInventoryProvider
from backend.social_inventory.repository import SocialInventoryRepository
from backend.social_inventory.schemas import StartProviderRunRequest

ProviderFactory = Callable[[], SocialInventoryProvider]


class SocialInventoryTaskRunner:
    def __init__(self, session: Session, *, settings: Settings | None = None, provider_factory: ProviderFactory | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.provider_factory = provider_factory or (lambda: ApifyProvider(self.settings))

    def execute(self, run: SocialInventoryRun) -> None:
        if run.status == "cancelled": return
        try:
            asyncio.run(self._execute(run))
        except SocialInventoryError as exc:
            self._failure(run, exc)
        except Exception:
            self._failure(run, SocialInventoryError("SOCIAL_PROVIDER_FAILED", "The inventory run failed unexpectedly.", retryable=True, status_code=500))

    async def _execute(self, run: SocialInventoryRun) -> None:
        provider = self.provider_factory()
        repo = SocialInventoryRepository(self.session, run.owner_id)
        try:
            if run.provider_run_id is None:
                run.status = "starting"; run.started_at = run.started_at or datetime.now(UTC); self.session.commit()
                started = await provider.start_run(StartProviderRunRequest(platform=run.source.platform, source_url=run.source.canonical_url, max_items=run.max_items, date_from=run.date_from, date_to=run.date_to, include_comments=run.include_comments, max_comments_per_post=run.max_comments_per_post, request_id=run.request_id))
                run.provider_run_id = started.id; run.provider_dataset_id = started.dataset_id; run.provider_metadata = started.metadata; run.status = "running"; repo.release(run, 2); self.session.commit(); return
            if run.status in {"starting", "running"}:
                current = await provider.get_run(run.provider_run_id)
                run.provider_dataset_id = current.dataset_id or run.provider_dataset_id
                run.provider_metadata = {**(run.provider_metadata or {}), **current.metadata}
                if current.status == "running":
                    run.status = "running"; repo.release(run, 3); self.session.commit(); return
                if current.status == "cancelled":
                    run.status = "cancelled"; run.finished_at = datetime.now(UTC); repo.release(run); self.session.commit(); return
                if current.status == "failed":
                    message = current.error_message or "The provider run failed."
                    unavailable = any(marker in message.casefold() for marker in ("private", "login", "captcha", "unavailable"))
                    raise SocialInventoryError("SOCIAL_PRIVATE_OR_UNAVAILABLE" if unavailable else "SOCIAL_PROVIDER_FAILED", message, retryable=False)
                run.status = "importing"; self.session.commit()
            if run.status == "importing":
                remaining = run.max_items - run.items_seen
                if remaining <= 0:
                    self._success(run, repo); return
                page = await provider.get_items(run.provider_run_id, offset=run.import_offset, limit=min(self.settings.social_inventory_page_size, remaining))
                warnings = list(run.warnings or [])
                for raw in page.items:
                    try:
                        normalized = normalize_item(run.source.platform, raw, run.provider)
                        _, created, updated, comments = repo.upsert_item(run.source_id, normalized)
                        run.items_seen += 1; run.items_created += int(created); run.items_updated += int(updated); run.comments_created += comments
                    except (ValueError, TypeError) as exc:
                        warnings.append({"offset": run.import_offset + run.items_seen, "message": str(exc)[:300]})
                run.warnings = warnings; run.import_offset += len(page.items); self.session.commit()
                if page.has_more and run.items_seen < run.max_items:
                    repo.release(run, 1); self.session.commit(); return
                self._success(run, repo, partial=bool(warnings))
        finally:
            close = getattr(provider, "close", None)
            if close: await close()

    def _success(self, run: SocialInventoryRun, repo: SocialInventoryRepository, partial: bool = False) -> None:
        run.status = "partial" if partial else "succeeded"; run.finished_at = datetime.now(UTC); run.source.last_synced_at = run.finished_at
        if run.source.sync_enabled and run.source.sync_interval_minutes:
            from datetime import timedelta
            run.source.next_sync_at = run.finished_at + timedelta(minutes=run.source.sync_interval_minutes)
        repo.release(run); self.session.commit()

    def _failure(self, run: SocialInventoryRun, exc: SocialInventoryError) -> None:
        repo = SocialInventoryRepository(self.session, run.owner_id)
        run.attempts += 1
        run.error_code = exc.code; run.error_message = exc.message
        if exc.retryable and run.attempts < self.settings.social_inventory_max_retries:
            run.status = "running" if run.provider_run_id else "queued"; repo.release(run, min(2 ** max(run.attempts, 1), 60))
        else:
            run.status = "partial" if run.items_created or run.items_updated else "failed"; run.finished_at = datetime.now(UTC); repo.release(run)
        self.session.commit()
