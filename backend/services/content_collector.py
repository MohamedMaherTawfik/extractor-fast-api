"""Universal, platform-neutral content collection orchestration."""

import logging
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.connectors.config import ConnectorConfig
from backend.connectors.pagination import PaginationState
from backend.connectors.registry import ConnectorEntry, ConnectorRegistry, connector_registry
from backend.connectors.resilience import RateLimiter, RetryPolicy
from backend.connectors.url_router import PlatformURLKind, route_platform_url
from backend.core.enums import CollectionRunStatus, Platform
from backend.core.exceptions import (
    ConnectorPermissionError,
    ConnectorRateLimitError,
    ConnectorUnavailableError,
    ContentNormalizationError,
    InvalidAccountError,
    NotFoundError,
)
from backend.core.paths import paths
from backend.db.base import utc_now
from backend.db.models.collection_run import CollectionRun
from backend.db.models.creator import Creator
from backend.db.models.platform_account import PlatformAccount
from backend.repositories.collection_run_repository import CollectionRunRepository
from backend.repositories.content_repository import ContentRepository
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import PlatformAccountRepository
from backend.schemas.collection import CollectionOptions
from backend.schemas.content import NormalizedContent
from backend.services.media_download import MediaDownloader, UnavailableMediaDownloader
from backend.services.raw_storage import RawContentStore, redact_sensitive


logger = logging.getLogger(__name__)
RetryFactory = Callable[[ConnectorConfig], RetryPolicy]
RateLimiterFactory = Callable[[ConnectorConfig], RateLimiter]


class UniversalContentCollector:
    """Synchronous executor behind a persistent, worker-ready job boundary."""

    def __init__(
        self,
        session: Session,
        *,
        registry: ConnectorRegistry = connector_registry,
        raw_store: RawContentStore | None = None,
        media_downloader: MediaDownloader | None = None,
        retry_factory: RetryFactory | None = None,
        rate_limiter_factory: RateLimiterFactory | None = None,
    ) -> None:
        self._session = session
        self.registry = registry
        self.raw_store = raw_store or RawContentStore()
        self.media_downloader = media_downloader or UnavailableMediaDownloader()
        self.retry_factory = retry_factory or (
            lambda config: RetryPolicy(
                max_retries=config.max_retries,
                initial_delay=config.backoff_initial_seconds,
                max_delay=config.backoff_max_seconds,
            )
        )
        self.rate_limiter_factory = rate_limiter_factory or (
            lambda config: RateLimiter(config.rate_limit_per_minute)
        )
        self.creators = CreatorRepository(session)
        self.accounts = PlatformAccountRepository(session)
        self.content = ContentRepository(session)
        self.runs = CollectionRunRepository(session)

    def collect_creator(
        self,
        creator_id: int,
        options: CollectionOptions | None = None,
    ) -> list[CollectionRun]:
        creator = self.creators.get(creator_id)
        if creator is None:
            raise NotFoundError(f"Creator {creator_id} was not found")
        effective_options = options or CollectionOptions()
        return [
            self.collect_account(account.id, effective_options)
            for account in self.accounts.list_for_creator(creator_id)
        ]

    def collect_account(
        self,
        account_id: int,
        options: CollectionOptions | None = None,
    ) -> CollectionRun:
        account = self.accounts.get(account_id)
        if account is None:
            raise NotFoundError(f"Platform account {account_id} was not found")
        creator = self._session.get(Creator, account.creator_id)
        if creator is None:
            raise NotFoundError(f"Creator {account.creator_id} was not found")
        effective_options = options or CollectionOptions()
        run = self.runs.create(
            creator_id=creator.id,
            platform_account_id=account.id,
            connector=account.platform.value,
            options=effective_options.model_dump(mode="json"),
        )
        entry = self.registry.describe(account.platform)
        self._execute_account(run, creator, account, entry, effective_options)
        return run

    def collect_url(
        self,
        url: str,
        options: CollectionOptions | None = None,
    ) -> CollectionRun:
        route = route_platform_url(url)
        effective_options = options or CollectionOptions()
        if route.kind is PlatformURLKind.PROFILE:
            matches = self.accounts.find_matches(
                platform=route.platform,
                username=route.reference,
                platform_user_id=None,
                profile_url=url,
            )
            if len(matches) != 1:
                raise InvalidAccountError(
                    "Profile URL must match exactly one saved platform account"
                )
            run = self.collect_account(matches[0].id, effective_options)
            run.source_url = url
            self._session.flush()
            return run
        return self._collect_content_url(url, route.platform, effective_options)

    def get_run(self, run_id: int) -> CollectionRun:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Collection run {run_id} was not found")
        return run

    def list_runs(self, *, offset: int = 0, limit: int = 100) -> list[CollectionRun]:
        return self.runs.list(offset=offset, limit=limit)

    def _execute_account(
        self,
        run: CollectionRun,
        creator: Creator,
        account: PlatformAccount,
        entry: ConnectorEntry,
        options: CollectionOptions,
    ) -> None:
        self._start(run)
        try:
            connector = self.registry.get(account.platform)
            retry = self.retry_factory(entry.config)
            limiter = self.rate_limiter_factory(entry.config)
            identifier = account.platform_user_id or account.username or account.profile_url
            if not identifier:
                raise InvalidAccountError("Saved account has no resolvable identifier")
            limiter.acquire()
            resolved = retry.run(
                lambda: connector.resolve_account(
                    identifier,
                    timeout=entry.config.timeout_seconds,
                ),
                self._retry_callback(run),
            )
            if not isinstance(resolved, Mapping):
                raise InvalidAccountError("Connector returned an invalid account payload")
            logger.info(
                "account_resolved job=%s connector=%s",
                run.job_uid,
                run.connector,
            )

            pagination = (
                PaginationState.model_validate(account.last_cursor)
                if account.last_cursor and not account.collection_completed
                else None
            )
            since = options.since_date or account.last_collected_at
            max_items = min(
                options.max_items or entry.config.max_items_per_run,
                entry.config.max_items_per_run,
            )
            seen_states: set[str] = set()
            completed = False

            while run.items_found < max_items:
                limiter.acquire()
                remaining = max_items - run.items_found
                page = retry.run(
                    lambda: connector.fetch_content_list(
                        resolved,
                        pagination=pagination,
                        since=since,
                        limit=remaining,
                        timeout=entry.config.timeout_seconds,
                    ),
                    self._retry_callback(run),
                )
                logger.info(
                    "page_fetched job=%s items=%d has_next=%s",
                    run.job_uid,
                    len(page.items),
                    page.next_state is not None,
                )
                for raw_content in page.items[:remaining]:
                    self._process_raw_item(
                        run=run,
                        creator=creator,
                        account=account,
                        raw_content=raw_content,
                        connector=connector,
                        config=entry.config,
                        options=options,
                    )
                next_state = page.next_state
                completed = page.collection_completed or next_state is None
                if completed:
                    pagination = None
                    break
                fingerprint = next_state.fingerprint()
                if fingerprint in seen_states:
                    raise InvalidAccountError("Connector repeated a pagination state")
                seen_states.add(fingerprint)
                pagination = next_state
                state_data = pagination.model_dump(exclude_none=True)
                account.last_cursor = state_data
                run.cursor_state = state_data
                self._session.flush()

            account.collection_completed = completed
            if completed:
                account.last_cursor = None
                run.cursor_state = None
                account.last_collected_at = utc_now()
            self._finish(
                run,
                CollectionRunStatus.PARTIAL
                if run.items_failed
                else CollectionRunStatus.COMPLETED,
            )
        except Exception as exc:
            self._record_run_error(run, exc)
            status = (
                CollectionRunStatus.PARTIAL
                if run.items_created or run.items_updated or run.items_skipped
                else CollectionRunStatus.FAILED
            )
            self._finish(run, status)

    def _collect_content_url(
        self,
        url: str,
        platform: Platform,
        options: CollectionOptions,
    ) -> CollectionRun:
        run = self.runs.create(
            connector=platform.value,
            source_url=url,
            options=options.model_dump(mode="json"),
        )
        self._start(run)
        raw_path: str | None = None
        try:
            entry = self.registry.describe(platform)
            connector = self.registry.get(platform)
            retry = self.retry_factory(entry.config)
            limiter = self.rate_limiter_factory(entry.config)
            limiter.acquire()
            raw_content = retry.run(
                lambda: connector.fetch_content_item(
                    url,
                    timeout=entry.config.timeout_seconds,
                ),
                self._retry_callback(run),
            )
            raw_path = self.raw_store.store(
                platform=platform,
                creator_uid="UNASSIGNED",
                raw_content=raw_content,
            )
            normalized = self._normalize(connector.normalize(raw_content), platform)
            account = self._resolve_content_account(normalized)
            creator = self._session.get(Creator, account.creator_id)
            if creator is None:
                raise InvalidAccountError("Matched content account has no creator")
            run.creator_id = creator.id
            run.platform_account_id = account.id
            raw_path = self.raw_store.rehome(raw_path, creator_uid=creator.creator_uid)
            run.items_found = 1
            self._save_normalized(
                run=run,
                creator=creator,
                account=account,
                normalized=normalized,
                raw_path=raw_path,
                config=entry.config,
                options=options,
            )
            self._finish(
                run,
                CollectionRunStatus.PARTIAL
                if run.items_failed
                else CollectionRunStatus.COMPLETED,
            )
        except Exception as exc:
            self._record_run_error(run, exc)
            self._finish(run, CollectionRunStatus.FAILED)
        return run

    def _process_raw_item(
        self,
        *,
        run: CollectionRun,
        creator: Creator,
        account: PlatformAccount,
        raw_content: Mapping[str, Any],
        connector: Any,
        config: ConnectorConfig,
        options: CollectionOptions,
    ) -> None:
        run.items_found += 1
        try:
            raw_path = self.raw_store.store(
                platform=account.platform,
                creator_uid=creator.creator_uid,
                raw_content=raw_content,
            )
            normalized = self._normalize(
                connector.normalize(raw_content),
                account.platform,
            )
            logger.info(
                "content_normalized job=%s connector=%s",
                run.job_uid,
                run.connector,
            )
            self._save_normalized(
                run=run,
                creator=creator,
                account=account,
                normalized=normalized,
                raw_path=raw_path,
                config=config,
                options=options,
            )
        except Exception as exc:
            run.items_failed += 1
            self._append_error(run, exc)

    def _save_normalized(
        self,
        *,
        run: CollectionRun,
        creator: Creator,
        account: PlatformAccount,
        normalized: NormalizedContent,
        raw_path: str,
        config: ConnectorConfig,
        options: CollectionOptions,
    ) -> None:
        local_media_path = None
        if options.download_media and normalized.media_url:
            try:
                local_media_path = self._download_media(
                    normalized,
                    creator,
                    config,
                )
            except Exception as exc:
                run.items_failed += 1
                self._append_error(run, exc)
        result = self.content.upsert(
            normalized,
            creator_id=creator.id,
            platform_account_id=account.id,
            raw_storage_path=raw_path,
            local_media_path=local_media_path,
        )
        if result.outcome == "created":
            run.items_created += 1
        elif result.outcome == "updated":
            run.items_updated += 1
        else:
            run.items_skipped += 1
        logger.info(
            "content_persisted job=%s outcome=%s",
            run.job_uid,
            result.outcome,
        )

    def _download_media(
        self,
        content: NormalizedContent,
        creator: Creator,
        config: ConnectorConfig,
    ) -> str:
        destination = paths.resolve_under(
            paths.media,
            Path(content.platform.value)
            / paths.safe_component(creator.creator_uid)
            / paths.safe_component(content.content_uid),
        )
        destination.mkdir(parents=True, exist_ok=True)
        downloaded = self.media_downloader.download(
            content.media_url or "",
            destination,
            config.timeout_seconds,
        ).resolve()
        if not downloaded.is_file() or not downloaded.is_relative_to(destination):
            raise ValueError("Media downloader returned an unmanaged file")
        return paths.relative(downloaded).as_posix()

    def _resolve_content_account(self, content: NormalizedContent) -> PlatformAccount:
        if content.platform_account_id:
            account = self.accounts.get(content.platform_account_id)
            if account and account.platform == content.platform:
                return account
        identity = content.account_identity
        if identity is None:
            raise InvalidAccountError(
                "Manual content URL did not include a saved account identity"
            )
        matches = self.accounts.find_matches(
            platform=content.platform,
            username=identity.username,
            platform_user_id=identity.platform_user_id,
            profile_url=identity.profile_url,
        )
        if len(matches) != 1:
            raise InvalidAccountError(
                "Manual content URL must match exactly one saved platform account"
            )
        return matches[0]

    @staticmethod
    def _normalize(value: Any, expected_platform: Platform) -> NormalizedContent:
        try:
            content = (
                value
                if isinstance(value, NormalizedContent)
                else NormalizedContent.model_validate(value)
            )
        except Exception as exc:
            raise ContentNormalizationError("Connector normalization failed") from exc
        if content.platform is not expected_platform:
            raise ContentNormalizationError("Connector returned the wrong platform")
        if content.raw_metadata is not None:
            content.raw_metadata = redact_sensitive(content.raw_metadata)
        return content

    def _retry_callback(
        self,
        run: CollectionRun,
    ) -> Callable[[int, float, Exception], None]:
        def callback(attempt: int, delay: float, exc: Exception) -> None:
            run.status = CollectionRunStatus.RETRYING
            self._session.flush()
            logger.warning(
                "collection_retry job=%s attempt=%d delay=%.3f error_type=%s",
                run.job_uid,
                attempt,
                delay,
                type(exc).__name__,
            )
            if isinstance(exc, ConnectorRateLimitError):
                logger.warning(
                    "connector_rate_limit job=%s connector=%s",
                    run.job_uid,
                    run.connector,
                )
            run.status = CollectionRunStatus.RUNNING

        return callback

    def _start(self, run: CollectionRun) -> None:
        run.status = CollectionRunStatus.RUNNING
        run.started_at = utc_now()
        self._session.flush()
        logger.info(
            "collection_started job=%s connector=%s",
            run.job_uid,
            run.connector,
        )

    def _finish(self, run: CollectionRun, status: CollectionRunStatus) -> None:
        run.status = status
        run.completed_at = utc_now()
        self._session.flush()
        logger.info(
            "collection_finished job=%s status=%s found=%d created=%d updated=%d skipped=%d failed=%d",
            run.job_uid,
            status.value,
            run.items_found,
            run.items_created,
            run.items_updated,
            run.items_skipped,
            run.items_failed,
        )

    def _record_run_error(self, run: CollectionRun, exc: Exception) -> None:
        self._append_error(run, exc)
        run.error_summary = _safe_error_message(exc)
        logger.error(
            "collection_failed job=%s connector=%s error_type=%s",
            run.job_uid,
            run.connector,
            type(exc).__name__,
        )
        if isinstance(exc, ConnectorPermissionError):
            logger.error(
                "connector_permission_error job=%s connector=%s",
                run.job_uid,
                run.connector,
            )

    @staticmethod
    def _append_error(run: CollectionRun, exc: Exception) -> None:
        errors = list(run.errors or [])
        errors.append(
            {
                "type": type(exc).__name__,
                "message": _safe_error_message(exc),
            }
        )
        run.errors = errors


_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|bearer|token|secret|password|cookie|api[_-]?key)\s*[:=]\s*\S+"
)


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, ConnectorUnavailableError):
        return f"{exc.platform} connector is {exc.availability}"
    message = str(exc)[:500] or type(exc).__name__
    return _SECRET_PATTERN.sub(r"\1=[REDACTED]", message)
