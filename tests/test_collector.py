from datetime import UTC, datetime
from pathlib import Path

from backend.connectors.base import BaseConnector
from backend.connectors.config import ConnectorConfig
from backend.connectors.pagination import ContentPage, PaginationState
from backend.connectors.registry import ConnectorRegistry
from backend.connectors.resilience import RateLimiter, RetryPolicy
from backend.core.enums import (
    CollectionRunStatus,
    ConnectorAvailability,
    ContentType,
    Platform,
)
from backend.core.exceptions import ConnectorPermissionError, ConnectorTemporaryError
from backend.core.paths import paths
from backend.db.models.content_item import ContentItem
from backend.db.models.platform_account import PlatformAccount
from backend.db.session import session_scope
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import PlatformAccountRepository
from backend.schemas.collection import CollectionOptions
from backend.schemas.content import ContentAccountIdentity, NormalizedContent
from backend.services.content_collector import UniversalContentCollector
from backend.services.media_download import MediaDownloader


class MockConnector(BaseConnector):
    def __init__(self, platform: Platform, *, fail_once: bool = False) -> None:
        self.platform = platform
        self.fail_once = fail_once
        self.failed = False
        self.calls = []
        self.views = 10
        self.permission_denied = False

    def resolve_account(self, identifier, *, timeout=None):
        if self.permission_denied:
            raise ConnectorPermissionError("permission denied")
        return {"identifier": identifier}

    def fetch_profile(self, account, *, timeout=None):
        return {"profile": account}

    def fetch_content_list(
        self,
        account,
        *,
        pagination=None,
        since=None,
        limit=None,
        timeout=None,
    ):
        self.calls.append((pagination, since, limit))
        if self.fail_once and not self.failed:
            self.failed = True
            raise ConnectorTemporaryError("temporary")
        if pagination and pagination.cursor == "page-2":
            return ContentPage([{"id": "two", "views": 20}])
        return ContentPage(
            [{"id": "one", "views": self.views, "secret": "hidden"}],
            next_state=PaginationState(cursor="page-2"),
            collection_completed=False,
        )

    def fetch_content_item(self, content_id, *, timeout=None):
        return {
            "id": "manual",
            "views": 5,
            "username": "mock_user",
            "source_url": content_id,
        }

    def normalize(self, raw_content):
        identity = None
        if raw_content.get("username"):
            identity = ContentAccountIdentity(username=raw_content["username"])
        content_id = raw_content["id"]
        return NormalizedContent(
            platform=self.platform,
            platform_content_id=content_id,
            content_type=ContentType.POST,
            source_url=raw_content.get(
                "source_url",
                f"https://example.invalid/{self.platform.value}/{content_id}",
            ),
            caption=f"caption-{content_id}",
            views=raw_content.get("views"),
            media_url=f"https://media.invalid/{content_id}.jpg",
            account_identity=identity,
        )


class MockMediaDownloader(MediaDownloader):
    def __init__(self) -> None:
        self.destinations = []

    def download(self, url: str, destination: Path, timeout: float) -> Path:
        self.destinations.append(destination)
        target = destination / "asset.bin"
        target.write_bytes(b"mock media")
        return target


def configured_registry(*connectors: MockConnector) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    for connector in connectors:
        registry.register(
            connector.platform,
            connector,
            ConnectorConfig(
                enabled=True,
                availability=ConnectorAvailability.CONFIGURED,
                rate_limit_per_minute=1_000_000,
                max_retries=2,
                backoff_initial_seconds=0,
                backoff_max_seconds=0,
                max_items_per_run=100,
            ),
        )
    return registry


def create_account(session, platform=Platform.INSTAGRAM, username="mock_user"):
    creator = CreatorRepository(session).create({"display_name": f"{platform} creator"})
    account = PlatformAccountRepository(session).create(
        creator.id,
        {"platform": platform, "username": username},
    )
    return creator, account


def collector(session, registry, media_downloader=None):
    return UniversalContentCollector(
        session,
        registry=registry,
        media_downloader=media_downloader,
        retry_factory=lambda config: RetryPolicy(
            config.max_retries,
            config.backoff_initial_seconds,
            config.backoff_max_seconds,
            sleep=lambda delay: None,
        ),
        rate_limiter_factory=lambda config: RateLimiter(
            config.rate_limit_per_minute,
            sleep=lambda delay: None,
        ),
    )


def test_pagination_resume_raw_preservation_and_incremental_dedup() -> None:
    connector = MockConnector(Platform.INSTAGRAM)
    registry = configured_registry(connector)
    with session_scope() as session:
        creator, account = create_account(session)
        service = collector(session, registry)

        first = service.collect_account(account.id, CollectionOptions(max_items=1))
        assert first.status is CollectionRunStatus.COMPLETED
        assert first.items_created == 1
        assert account.collection_completed is False
        assert account.last_cursor == {"cursor": "page-2"}

        second = service.collect_account(account.id, CollectionOptions())
        assert second.items_created == 1
        assert connector.calls[-1][0].cursor == "page-2"
        assert account.collection_completed is True
        assert account.last_collected_at is not None

        connector.views = 11
        third = service.collect_account(account.id, CollectionOptions())
        assert third.items_updated == 1
        assert connector.calls[-1][1] is not None

        fourth = service.collect_account(account.id, CollectionOptions())
        assert fourth.items_skipped == 2

        stored = session.query(ContentItem).filter_by(platform_content_id="one").one()
        raw_file = paths.resolve_under(paths.project_root, stored.raw_storage_path)
        raw_text = raw_file.read_text(encoding="utf-8")
        assert '"secret": "[REDACTED]"' in raw_text
        assert stored.views == 11
        assert stored.likes is None


def test_optional_media_download_is_separate_and_project_relative() -> None:
    connector = MockConnector(Platform.TIKTOK)
    downloader = MockMediaDownloader()
    with session_scope() as session:
        _, account = create_account(session, Platform.TIKTOK)
        run = collector(
            session,
            configured_registry(connector),
            downloader,
        ).collect_account(
            account.id,
            CollectionOptions(max_items=1, download_media=True),
        )
        item = session.query(ContentItem).one()

        assert run.items_created == 1
        assert item.local_media_path.startswith("data/media/tiktok/")
        assert item.raw_storage_path.startswith("data/raw/tiktok/")
        assert not Path(item.local_media_path).is_absolute()
        assert downloader.destinations


def test_media_failure_keeps_collected_metadata_and_marks_partial() -> None:
    connector = MockConnector(Platform.TIKTOK)
    with session_scope() as session:
        _, account = create_account(session, Platform.TIKTOK)
        run = collector(session, configured_registry(connector)).collect_account(
            account.id,
            CollectionOptions(max_items=1, download_media=True),
        )

        assert run.status is CollectionRunStatus.PARTIAL
        assert run.items_created == 1
        assert run.items_failed == 1
        assert session.query(ContentItem).one().local_media_path is None


def test_retry_jobs_permission_failure_and_creator_wide_collection() -> None:
    instagram = MockConnector(Platform.INSTAGRAM, fail_once=True)
    youtube = MockConnector(Platform.YOUTUBE)
    with session_scope() as session:
        creator, first_account = create_account(session)
        second_account = PlatformAccountRepository(session).create(
            creator.id,
            {"platform": Platform.YOUTUBE, "username": "youtube_user"},
        )
        service = collector(session, configured_registry(instagram, youtube))
        runs = service.collect_creator(creator.id, CollectionOptions(max_items=1))

        assert len(runs) == 2
        assert all(run.status is CollectionRunStatus.COMPLETED for run in runs)
        assert instagram.failed is True
        assert service.get_run(runs[0].id).job_uid.startswith("JOB_")
        assert len(service.list_runs()) == 2

        instagram.permission_denied = True
        failed = service.collect_account(first_account.id, CollectionOptions())
        assert failed.status is CollectionRunStatus.FAILED
        assert failed.errors[0]["type"] == "ConnectorPermissionError"
        assert second_account.id is not None


def test_manual_content_url_matches_saved_account_and_rehomes_raw() -> None:
    connector = MockConnector(Platform.INSTAGRAM)
    with session_scope() as session:
        creator, _ = create_account(session)
        run = collector(session, configured_registry(connector)).collect_url(
            "https://instagram.com/p/manual",
            CollectionOptions(),
        )
        item = session.query(ContentItem).one()

        assert run.status is CollectionRunStatus.COMPLETED
        assert run.source_url == "https://instagram.com/p/manual"
        assert run.items_found == 1
        assert f"/{creator.creator_uid}/" in item.raw_storage_path
        assert "UNASSIGNED" not in item.raw_storage_path


def test_deduplication_never_merges_across_platforms() -> None:
    instagram = MockConnector(Platform.INSTAGRAM)
    youtube = MockConnector(Platform.YOUTUBE)
    with session_scope() as session:
        first_creator, first = create_account(session, Platform.INSTAGRAM, "first")
        second_creator, second = create_account(session, Platform.YOUTUBE, "second")
        service = collector(session, configured_registry(instagram, youtube))
        service.collect_account(first.id, CollectionOptions(max_items=1))
        service.collect_account(second.id, CollectionOptions(max_items=1))

        items = session.query(ContentItem).all()
        assert len(items) == 2
        assert {item.platform for item in items} == {
            Platform.INSTAGRAM,
            Platform.YOUTUBE,
        }
        assert first_creator.id != second_creator.id


def test_unconfigured_connector_creates_explicit_failed_job() -> None:
    with session_scope() as session:
        _, account = create_account(session, Platform.FACEBOOK)
        run = collector(session, ConnectorRegistry()).collect_account(account.id)

        assert run.status is CollectionRunStatus.FAILED
        assert run.error_summary == "facebook connector is permission_required"
