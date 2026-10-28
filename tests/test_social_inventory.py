import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete, func, select

from backend.core.config import Settings
from backend.db.models.social_inventory import SocialInventoryItem, SocialInventoryMetricSnapshot, SocialInventorySource
from backend.db.session import session_scope
from backend.social_inventory.exceptions import SocialInventoryError
from backend.social_inventory.normalizer import normalize_item, sanitize_provider_response
from backend.social_inventory.providers.apify import ApifyProvider
from backend.social_inventory.repository import SocialInventoryRepository
from backend.social_inventory.schemas import ProviderItemsPage, ProviderRun, SourceCreate
from backend.social_inventory.service import SocialInventoryService
from backend.social_inventory.tasks import SocialInventoryTaskRunner
from backend.social_inventory.url_validation import validate_social_url


FIXTURES = Path(__file__).parent / "fixtures" / "social_inventory"
TEST_OWNER = "test-social-inventory"


@pytest.fixture(autouse=True)
def isolated_social_inventory_owner():
    from backend.main import app
    from backend.social_inventory.api import current_owner

    with session_scope() as session:
        session.execute(delete(SocialInventorySource).where(SocialInventorySource.owner_id == TEST_OWNER))
    previous = app.dependency_overrides.get(current_owner)
    app.dependency_overrides[current_owner] = lambda: TEST_OWNER
    yield
    with session_scope() as session:
        session.execute(delete(SocialInventorySource).where(SocialInventorySource.owner_id == TEST_OWNER))
    if previous is None:
        app.dependency_overrides.pop(current_owner, None)
    else:
        app.dependency_overrides[current_owner] = previous


def instagram_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def configured_settings(**values) -> Settings:
    return Settings(_env_file=None, apify_api_token="secret-token", apify_instagram_actor_id="test/instagram", social_inventory_max_retries=0, **values)


@pytest.mark.parametrize("url", [
    "http://instagram.com/example", "https://127.0.0.1/example",
    "https://user:pass@instagram.com/example", "https://evil.example/example",
    "https://instagram.com.evil.example/example", "https://instagram.com:444/example",
])
def test_url_validation_rejects_ssrf_and_untrusted_urls(url):
    with pytest.raises(SocialInventoryError) as error:
        validate_social_url(url)
    assert error.value.code == "SOCIAL_INVALID_URL"


def test_url_validation_detects_and_canonicalizes_platform():
    url, platform = validate_social_url("https://www.twitter.com/example/?utm_source=x&tab=posts#top")
    assert platform == "x"
    assert url == "https://x.com/example/?tab=posts"


def test_normalizer_preserves_null_metrics_and_redacts_secrets():
    item = normalize_item("instagram", {"id": "p1", "url": "https://instagram.com/p/p1/", "caption": "hello #world", "authorization": "Bearer secret", "author": {"username": "demo", "cookie": "bad"}})
    assert item.metrics.views is None
    assert item.hashtags == ["world"]
    assert item.provider_response["authorization"] == "[REDACTED]"
    assert item.provider_response["author"]["cookie"] == "[REDACTED]"


def test_instagram_reel_maps_actual_apify_fields():
    raw = instagram_fixture("instagram_reel_apify_sanitized.json")
    raw["accessToken"] = "must-not-survive"
    item = normalize_item("instagram", raw)
    assert item.content_type == "video"
    assert item.metrics.likes == 3865
    assert item.metrics.views == 139484
    assert item.metrics.comments == 11
    assert len(item.media) == 1
    assert item.media[0].type == "video"
    assert item.media[0].thumbnail_url == raw["displayUrl"]
    assert item.media[0].width == 1080
    assert item.media[0].height == 1920
    assert item.media[0].duration_seconds == 24.48
    assert item.media[0].url_status == "observed_temporary"
    assert item.canonical_url == "https://www.instagram.com/p/De94J5It_L-/"
    assert item.author.external_id == "52151791875"
    assert item.author.username == "eldaheeh"
    assert item.author.display_name == "ElDa7ee7"
    assert item.author.profile_url == "https://www.instagram.com/eldaheeh/"
    assert item.author.avatar_url is None
    assert item.author.followers_count is None
    assert item.author.verified is None
    assert set(item.provider_response) == set(raw)
    assert item.provider_response["accessToken"] == "[REDACTED]"


def test_instagram_image_post_and_author_metadata():
    raw = instagram_fixture("instagram_image_apify_sanitized.json")
    item = normalize_item("instagram", raw)
    assert item.content_type == "image"
    assert [media.type for media in item.media] == ["image"]
    assert item.media[0].url == raw["displayUrl"]
    assert item.media[0].width == 1080
    assert item.media[0].height == 1080
    assert item.author.profile_url == "https://www.instagram.com/valid.user_name/"
    assert item.author.avatar_url == raw["profilePicUrl"]
    assert item.author.followers_count == 1234
    assert item.author.verified is True


def test_instagram_carousel_maps_each_child_media():
    item = normalize_item("instagram", instagram_fixture("instagram_carousel_apify_sanitized.json"))
    assert item.content_type == "carousel"
    assert [media.type for media in item.media] == ["image", "video"]
    assert item.media[1].thumbnail_url.endswith("carousel-video-thumbnail.jpg")
    assert item.media[1].duration_seconds == 9.5
    assert all(media.url_status == "observed_temporary" for media in item.media)


def test_instagram_missing_metrics_remain_null_and_invalid_username_has_no_profile_url():
    item = normalize_item("instagram", {"id": "missing", "shortCode": "MISSING", "type": "Image", "displayUrl": "https://scontent.cdninstagram.com/sanitized/missing.jpg", "ownerUsername": "not a valid username!"})
    assert item.metrics.model_dump() == {"views": None, "likes": None, "comments": None, "shares": None, "saves": None}
    assert item.author.profile_url is None
    assert item.canonical_url == "https://www.instagram.com/p/MISSING/"


@pytest.mark.parametrize(("alias", "expected"), [("videoViewCount", 91), ("videoPlayCount", 92), ("views", 93), ("viewCount", 94), ("playCount", 95)])
def test_instagram_view_count_aliases(alias, expected):
    raw = {"id": alias, "url": f"https://www.instagram.com/p/{alias}/", "type": "Video", "videoUrl": "https://scontent.cdninstagram.com/sanitized/video.mp4", alias: expected}
    assert normalize_item("instagram", raw).metrics.views == expected


def test_instagram_upsert_preserves_first_seen_updates_last_seen_and_snapshots():
    first_seen = datetime(2026, 10, 26, 18, 1, tzinfo=UTC)
    second_seen = datetime(2026, 10, 28, 19, 2, tzinfo=UTC)
    raw = instagram_fixture("instagram_reel_apify_sanitized.json")
    with session_scope() as session:
        repo = SocialInventoryRepository(session, TEST_OWNER)
        source = repo.get_or_create_source(provider="apify", platform="instagram", source_url="https://www.instagram.com/eldaheeh/", canonical_url="https://instagram.com/eldaheeh/", settings={})
        first = normalize_item("instagram", raw).model_copy(update={"observed_at": first_seen})
        item, created, updated, _ = repo.upsert_item(source.id, first)
        assert created is True and updated is False
        item_id = item.id
        changed = {**raw, "likesCount": raw["likesCount"] + 10, "videoPlayCount": raw["videoPlayCount"] + 100}
        second = normalize_item("instagram", changed).model_copy(update={"observed_at": second_seen})
        same_item, created, updated, _ = repo.upsert_item(source.id, second)
        assert created is False and updated is True
        assert same_item.id == item_id
        assert same_item.first_observed_at == first_seen
        assert same_item.last_observed_at == second_seen
        assert session.scalar(
            select(func.count()).select_from(SocialInventoryItem).where(SocialInventoryItem.source_id == source.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(SocialInventoryMetricSnapshot).where(SocialInventoryMetricSnapshot.item_id == item_id)
        ) == 2


class FakeProvider:
    def __init__(self, likes=2): self.likes = likes
    async def start_run(self, request): return ProviderRun(id="run-1", status="starting", dataset_id="dataset-1")
    async def get_run(self, provider_run_id): return ProviderRun(id=provider_run_id, status="succeeded", dataset_id="dataset-1")
    async def get_items(self, provider_run_id, *, offset=0, limit=100):
        return ProviderItemsPage(items=[{"id": "p1", "url": "https://instagram.com/p/p1/", "caption": "=formula", "likeCount": self.likes, "viewCount": 10, "author": {"username": "demo"}}], offset=offset, limit=limit, has_more=False)


def _create_run(settings):
    with session_scope() as session:
        _, run = SocialInventoryService(session, TEST_OWNER, settings=settings).create_source_and_run(SourceCreate(source_url="https://www.instagram.com/demo/", platform="instagram", max_items=3), "request-1")
        return run.uuid


def _execute(uuid, provider, settings):
    with session_scope() as session:
        repo = SocialInventoryRepository(session, TEST_OWNER)
        run = repo.get_run(uuid)
        SocialInventoryTaskRunner(session, settings=settings, provider_factory=lambda: provider).execute(run)


def test_durable_run_imports_deduplicates_and_snapshots_metrics():
    settings = configured_settings()
    first = _create_run(settings)
    _execute(first, FakeProvider(2), settings)
    _execute(first, FakeProvider(2), settings)
    with session_scope() as session:
        source = SocialInventoryRepository(session, TEST_OWNER).list_sources()[0]
        second = SocialInventoryService(session, TEST_OWNER, settings=settings).sync(source).uuid
    _execute(second, FakeProvider(5), settings)
    _execute(second, FakeProvider(5), settings)
    with session_scope() as session:
        source = SocialInventoryRepository(session, TEST_OWNER).list_sources()[0]
        assert session.scalar(
            select(func.count()).select_from(SocialInventoryItem).where(SocialInventoryItem.source_id == source.id)
        ) == 1
        item = session.scalar(select(SocialInventoryItem).where(SocialInventoryItem.source_id == source.id))
        assert session.scalar(
            select(func.count()).select_from(SocialInventoryMetricSnapshot).where(SocialInventoryMetricSnapshot.item_id == item.id)
        ) == 2
        assert item.metrics["likes"] == 5
        runs = SocialInventoryRepository(session, TEST_OWNER).list_runs(0, 10)
        assert {run.status for run in runs} == {"succeeded"}


def test_owner_isolation_even_when_uuid_is_known():
    settings = configured_settings()
    uuid = _create_run(settings)
    with session_scope() as session:
        assert SocialInventoryRepository(session, TEST_OWNER).get_run(uuid) is not None
        assert SocialInventoryRepository(session, "another-owner").get_run(uuid) is None


def test_api_owner_dependency_blocks_known_source_uuid(api_request):
    from backend.main import app
    from backend.social_inventory.api import current_owner
    settings = configured_settings()
    with session_scope() as session:
        source, _ = SocialInventoryService(session, "owner-a", settings).create_source_and_run(SourceCreate(source_url="https://instagram.com/isolated/", platform="instagram", max_items=3))
        source_uuid = source.uuid
    previous = app.dependency_overrides.get(current_owner)
    app.dependency_overrides[current_owner] = lambda: "owner-b"
    try:
        assert api_request("GET", "/social-inventory/sources").json() == []
        response = api_request("GET", f"/social-inventory/sources/{source_uuid}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOCIAL_SOURCE_NOT_FOUND"
    finally:
        if previous is None:
            app.dependency_overrides.pop(current_owner, None)
        else:
            app.dependency_overrides[current_owner] = previous
        with session_scope() as cleanup_session:
            cleanup_session.execute(delete(SocialInventorySource).where(SocialInventorySource.owner_id == "owner-a"))


def test_csv_export_escapes_formula(api_request):
    settings = configured_settings()
    uuid = _create_run(settings)
    _execute(uuid, FakeProvider(), settings); _execute(uuid, FakeProvider(), settings)
    response = api_request("GET", "/social-inventory/exports/csv")
    assert response.status_code == 200
    assert "'=formula" in response.text
    assert "provider_response" not in response.text.splitlines()[0]


def test_missing_actor_error_does_not_leak_token():
    settings = Settings(_env_file=None, apify_api_token="secret-token", apify_instagram_actor_id=None)
    with session_scope() as session, pytest.raises(SocialInventoryError) as error:
        SocialInventoryService(session, settings=settings).create_source_and_run(SourceCreate(source_url="https://instagram.com/example/", platform="instagram", max_items=3))
    assert error.value.code == "SOCIAL_PLATFORM_NOT_CONFIGURED"
    assert "secret-token" not in error.value.message


def test_apify_uses_authorization_header_and_maps_status():
    seen = {}
    def handler(request: httpx.Request):
        seen["authorization"] = request.headers.get("Authorization")
        assert "token=" not in str(request.url)
        return httpx.Response(200, json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds"}})
    async def exercise():
        client = httpx.AsyncClient(base_url="https://api.apify.com/v2", transport=httpx.MockTransport(handler))
        provider = ApifyProvider(configured_settings(), client)
        run = await provider.get_run("run-1")
        await client.aclose()
        return run
    run = asyncio.run(exercise())
    assert seen["authorization"] == "Bearer secret-token"
    assert run.status == "succeeded"


def test_sanitizer_recurses_lists():
    assert sanitize_provider_response([{"sessionid": "private"}]) == [{"sessionid": "[REDACTED]"}]


@pytest.mark.parametrize(("status", "code"), [
    (401, "SOCIAL_PROVIDER_AUTH_FAILED"), (403, "SOCIAL_PROVIDER_AUTH_FAILED"),
    (429, "SOCIAL_PROVIDER_RATE_LIMITED"), (500, "SOCIAL_PROVIDER_FAILED"),
])
def test_apify_http_error_mapping(status, code):
    async def exercise():
        client = httpx.AsyncClient(base_url="https://api.apify.com/v2", transport=httpx.MockTransport(lambda request: httpx.Response(status)))
        try:
            with pytest.raises(SocialInventoryError) as error:
                await ApifyProvider(configured_settings(), client).get_run("run-1")
            return error.value
        finally:
            await client.aclose()
    assert asyncio.run(exercise()).code == code


def test_apify_timeout_mapping():
    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)
    async def exercise():
        client = httpx.AsyncClient(base_url="https://api.apify.com/v2", transport=httpx.MockTransport(timeout))
        try:
            with pytest.raises(SocialInventoryError) as error:
                await ApifyProvider(configured_settings(), client).get_run("run-1")
            return error.value
        finally:
            await client.aclose()
    assert asyncio.run(exercise()).code == "SOCIAL_PROVIDER_TIMEOUT"


def test_apify_dataset_page_uses_pagination_header():
    def handler(request):
        if "/actor-runs/" in request.url.path:
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds"}})
        return httpx.Response(200, headers={"X-Apify-Pagination-Total": "3"}, json=[{"id": "1"}, {"id": "2"}])
    async def exercise():
        client = httpx.AsyncClient(base_url="https://api.apify.com/v2", transport=httpx.MockTransport(handler))
        try: return await ApifyProvider(configured_settings(), client).get_items("run-1", offset=0, limit=2)
        finally: await client.aclose()
    page = asyncio.run(exercise())
    assert len(page.items) == 2
    assert page.has_more is True


def test_cancelled_run_is_terminal():
    settings = configured_settings(); uuid = _create_run(settings)
    with session_scope() as session:
        service = SocialInventoryService(session, TEST_OWNER, settings=settings)
        run = service.cancel(service.repo.get_run(uuid))
        assert run.status == "cancelled"


def test_jev_disabled_capability():
    from backend.social_inventory.providers.jev import JevSocialProvider
    assert JevSocialProvider(Settings(_env_file=None, jev_social_enabled=False)).capability()["enabled"] is False
