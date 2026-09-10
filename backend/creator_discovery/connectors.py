"""Compliant creator discovery adapters with explicit capability states."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

from backend.core.config import Settings, get_settings
from backend.creator_discovery.config import CreatorDiscoveryConfig, get_creator_discovery_config
from backend.creator_discovery.meta import META_API_SOURCE, MetaApiClient, MetaApiError
from backend.creator_discovery.normalization import NormalizedDiscoveryInput, normalize_profile_url
from backend.creator_discovery.quality import collection_status, data_completeness
from backend.schemas.creator_discovery import DiscoveryPlatform


@dataclass(slots=True)
class DiscoveredCandidate:
    platform: DiscoveryPlatform
    profile_url: str
    display_name: str | None = None
    username: str | None = None
    public_bio: str | None = None
    public_avatar_url: str | None = None
    followers: int | None = None
    following: int | None = None
    content_count: int | None = None
    verified: bool | None = None
    discovery_source: str = "UNKNOWN"
    source_id: str | None = None
    linked_social_urls: list[str] = field(default_factory=list)
    website: str | None = None
    profile_data: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    identity_status: str = "IDENTITY_RESOLVED"
    data_collection_status: str = "DATA_COLLECTION_REQUIRED"
    data_completeness: float = 0.0
    connector_requirement: str = "API_REQUIRED"

    def as_match_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveredContent:
    platform: DiscoveryPlatform
    content_url: str
    platform_content_id: str | None = None
    published_at: datetime | None = None
    title: str | None = None
    caption: str | None = None
    content_type: str = "UNKNOWN"
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    duration_seconds: float | None = None
    hashtags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "UNKNOWN"
    provenance: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class DiscoveryOutcome:
    status: str
    candidates: list[DiscoveredCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PlatformDiscoveryConnector(ABC):
    platform: DiscoveryPlatform

    @abstractmethod
    def capability(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def discover(self, value: NormalizedDiscoveryInput) -> DiscoveryOutcome:
        raise NotImplementedError

    def collect_recent(self, candidate: DiscoveredCandidate, limit: int) -> list[DiscoveredContent]:
        return []


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs if value}
        if tag.casefold() == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            if key and values.get("content"):
                self.meta[key] = values["content"]
        elif tag.casefold() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


class PublicPageMetadataFetcher:
    """Fetch only robots-permitted public metadata; never uses cookies or evasion."""

    user_agent = "EMY-CreatorDiscovery/1.0"

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> dict[str, str]:
        parsed = urlsplit(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rules = robotparser.RobotFileParser()
        try:
            response = httpx.get(
                robots_url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
                follow_redirects=True,
            )
            if response.status_code >= 400:
                return {}
            rules.set_url(robots_url)
            rules.parse(response.text.splitlines())
            if not rules.can_fetch(self.user_agent, url):
                return {}
            page = httpx.get(
                url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            page.raise_for_status()
        except (httpx.HTTPError, OSError):
            return {}
        parser = _MetadataParser()
        parser.feed(page.text[:2_000_000])
        return {
            "title": parser.meta.get("og:title") or " ".join(parser.title_parts).strip(),
            "description": parser.meta.get("og:description") or parser.meta.get("description") or "",
            "image": parser.meta.get("og:image") or "",
            "canonical_url": parser.meta.get("og:url") or str(page.url),
        }


class DirectURLConnector(PlatformDiscoveryConnector):
    def __init__(
        self,
        platform: DiscoveryPlatform,
        config: CreatorDiscoveryConfig | None = None,
    ) -> None:
        self.platform = platform
        self.config = config or get_creator_discovery_config()
        self.fetcher = PublicPageMetadataFetcher(self.config.execution.request_timeout_seconds)

    def capability(self) -> dict[str, Any]:
        values = self.config.platforms[self.platform.value]
        public_fetch = self.config.execution.allow_public_page_fetch
        return {
            "platform": self.platform,
            "configured": False,
            "name_discovery": values["name_discovery"],
            "direct_url": values["direct_url"],
            "profile_enumeration": "PUBLIC_PAGE" if public_fetch else "MANUAL_URL_REQUIRED",
            "content_sampling": values["content_sampling"],
            "detail": "Direct URLs resolve identity only unless permitted public metadata or an authorized API supplies actual evidence.",
        }

    def discover(self, value: NormalizedDiscoveryInput) -> DiscoveryOutcome:
        if value.kind != "PROFILE_URL" or value.platform is not self.platform or not value.url:
            return DiscoveryOutcome(self.capability()["name_discovery"])
        metadata = self.fetcher.fetch(value.url) if self.config.execution.allow_public_page_fetch else {}
        source = "public_profile_page" if metadata else "operator_supplied_url"
        retrieved_at = datetime.now(UTC).isoformat()
        candidate = DiscoveredCandidate(
            platform=self.platform,
            profile_url=value.url,
            display_name=metadata.get("title") or None,
            username=value.username,
            public_bio=metadata.get("description") or None,
            public_avatar_url=metadata.get("image") or None,
            discovery_source=source,
            source_id=value.username,
            profile_data={"page_metadata": metadata} if metadata else {},
            provenance=[{
                "source": source,
                "platform": self.platform.value,
                "source_url": value.url,
                "retrieved_at": retrieved_at,
                "fields": ["profile_url", "username"] + (["display_name", "public_bio", "public_avatar_url"] if metadata else []),
            }],
        )
        candidate.data_completeness = data_completeness(candidate)
        candidate.data_collection_status = collection_status(candidate.data_completeness)
        candidate.connector_requirement = str(self.capability()["content_sampling"])
        return DiscoveryOutcome("FOUND", [candidate])


class YouTubeConnector(DirectURLConnector):
    api_base = "https://www.googleapis.com/youtube/v3"

    def __init__(self, settings: Settings | None = None, config: CreatorDiscoveryConfig | None = None) -> None:
        super().__init__(DiscoveryPlatform.YOUTUBE, config)
        self.settings = settings or get_settings()
        self.api_key = self.settings.creator_discovery_youtube_api_key

    def capability(self) -> dict[str, Any]:
        result = super().capability()
        configured = bool(self.api_key)
        result.update(
            configured=configured,
            name_discovery="CONFIGURED" if configured else "API_REQUIRED",
            profile_enumeration="CONFIGURED" if configured else result["profile_enumeration"],
            content_sampling="CONFIGURED" if configured else "API_REQUIRED",
            detail="Official YouTube Data API v3 is configured." if configured else result["detail"],
        )
        return result

    def discover(self, value: NormalizedDiscoveryInput) -> DiscoveryOutcome:
        if not self.api_key:
            return super().discover(value)
        try:
            if value.kind == "PROFILE_URL" and value.platform is self.platform:
                channel_items = self._channels_for_profile(value)
                direct = True
            elif value.kind == "NAME":
                search = self._get("search", part="snippet", q=value.original, type="channel", maxResults=10)
                ids = [item.get("id", {}).get("channelId") for item in search.get("items", [])]
                channel_items = self._channel_details([item for item in ids if item])
                direct = False
            else:
                return DiscoveryOutcome("MANUAL_URL_REQUIRED")
            candidates = [self._candidate(item, direct=direct) for item in channel_items]
            return DiscoveryOutcome("FOUND" if candidates else "NOT_AVAILABLE", candidates)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return DiscoveryOutcome("API_ERROR", errors=[str(exc)[:500]])

    def collect_recent(self, candidate: DiscoveredCandidate, limit: int) -> list[DiscoveredContent]:
        if not self.api_key:
            return []
        playlist = candidate.profile_data.get("uploads_playlist")
        if not playlist:
            return []
        payload = self._get(
            "playlistItems", part="snippet,contentDetails", playlistId=playlist, maxResults=min(limit, 50)
        )
        items = payload.get("items", [])
        ids = [item.get("contentDetails", {}).get("videoId") for item in items]
        statistics: dict[str, dict[str, Any]] = {}
        if ids:
            videos = self._get("videos", part="statistics,contentDetails", id=",".join(ids))
            statistics = {item["id"]: item for item in videos.get("items", [])}
        results = []
        for item in items[:limit]:
            snippet = item.get("snippet", {})
            video_id = item.get("contentDetails", {}).get("videoId")
            detail = statistics.get(video_id, {})
            stats = detail.get("statistics", {})
            description = snippet.get("description") or None
            published = snippet.get("publishedAt") or item.get("contentDetails", {}).get("videoPublishedAt")
            results.append(DiscoveredContent(
                platform=self.platform,
                content_url=f"https://www.youtube.com/watch?v={video_id}",
                platform_content_id=video_id,
                published_at=_parse_datetime(published),
                title=snippet.get("title"),
                caption=description,
                content_type="VIDEO",
                views=_integer(stats.get("viewCount")),
                likes=_integer(stats.get("likeCount")),
                comments=_integer(stats.get("commentCount")),
                duration_seconds=_iso_duration_seconds(detail.get("contentDetails", {}).get("duration")),
                hashtags=sorted(set(re.findall(r"#([\w\u0600-\u06ff]+)", description or ""))),
                metadata={"privacy_status": item.get("status", {}).get("privacyStatus")},
                source="youtube_data_api_v3",
                provenance=[{
                    "source": "youtube_data_api_v3",
                    "platform": "youtube",
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }],
            ))
        return results

    def _channels_for_profile(self, value: NormalizedDiscoveryInput) -> list[dict[str, Any]]:
        path = [part for part in urlsplit(value.url or "").path.split("/") if part]
        if path[:1] == ["channel"] and len(path) > 1:
            return self._channel_details([path[1]])
        if value.username:
            payload = self._get("channels", part="snippet,statistics,contentDetails,brandingSettings", forHandle=value.username)
            if payload.get("items"):
                return list(payload["items"])
        search = self._get("search", part="snippet", q=value.username or value.original, type="channel", maxResults=5)
        ids = [item.get("id", {}).get("channelId") for item in search.get("items", [])]
        return self._channel_details([item for item in ids if item])

    def _channel_details(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        payload = self._get(
            "channels", part="snippet,statistics,contentDetails,brandingSettings", id=",".join(ids[:50])
        )
        return list(payload.get("items", []))

    def _candidate(self, item: dict[str, Any], *, direct: bool) -> DiscoveredCandidate:
        channel_id = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        branding = item.get("brandingSettings", {}).get("channel", {})
        thumbnails = snippet.get("thumbnails", {})
        avatar = next((thumbnails[key].get("url") for key in ("high", "medium", "default") if key in thumbnails), None)
        hidden = bool(stats.get("hiddenSubscriberCount"))
        source_url = f"https://www.youtube.com/channel/{channel_id}"
        candidate = DiscoveredCandidate(
            platform=self.platform,
            profile_url=source_url,
            display_name=snippet.get("title"),
            username=snippet.get("customUrl"),
            public_bio=snippet.get("description") or None,
            public_avatar_url=avatar,
            followers=None if hidden else _integer(stats.get("subscriberCount")),
            content_count=_integer(stats.get("videoCount")),
            verified=None,
            discovery_source="youtube_data_api_v3",
            source_id=channel_id,
            linked_social_urls=[],
            website=None,
            profile_data={
                "published_at": snippet.get("publishedAt"),
                "country": snippet.get("country"),
                "keywords": branding.get("keywords"),
                "uploads_playlist": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
                "direct_url_input": direct,
            },
            provenance=[{
                "source": "youtube_data_api_v3",
                "platform": "youtube",
                "source_url": source_url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "fields": ["display_name", "bio", "avatar", "followers", "content_count", "published_at"],
            }],
            connector_requirement="NONE",
        )
        candidate.data_completeness = data_completeness(candidate)
        candidate.data_collection_status = collection_status(candidate.data_completeness)
        return candidate

    def _get(self, resource: str, **params: Any) -> dict[str, Any]:
        params["key"] = self.api_key
        response = httpx.get(
            f"{self.api_base}/{resource}",
            params=params,
            timeout=self.config.execution.request_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("YouTube API returned an invalid payload")
        return payload


class _MetaConnector(DirectURLConnector):
    """Common capability and failure behavior for official Meta connectors."""

    def __init__(
        self,
        platform: DiscoveryPlatform,
        meta_client: MetaApiClient | None = None,
        config: CreatorDiscoveryConfig | None = None,
    ) -> None:
        super().__init__(platform, config)
        self.meta = meta_client or MetaApiClient()

    def _platform_validation(self):
        validation = self.meta.validate()
        return validation.instagram if self.platform is DiscoveryPlatform.INSTAGRAM else validation.facebook

    def capability(self) -> dict[str, Any]:
        base = super().capability()
        validation = self.meta.validate()
        platform = validation.instagram if self.platform is DiscoveryPlatform.INSTAGRAM else validation.facebook
        ready = platform.status == "READY"
        base.update(
            configured=self.meta.configured,
            status=platform.status,
            name_discovery="DIRECT_URL_REQUIRED" if ready else "API_REQUIRED",
            direct_url="CONFIGURED" if ready else "IDENTITY_ONLY",
            profile_enumeration="CONFIGURED" if ready else platform.status,
            content_sampling="CONFIGURED" if ready else platform.status,
            detail=platform.message,
            last_validation=validation.last_validation,
        )
        return base

    def _identity_fallback(
        self,
        value: NormalizedDiscoveryInput,
        status: str,
        message: str,
    ) -> DiscoveryOutcome:
        if value.kind != "PROFILE_URL" or value.platform is not self.platform:
            return DiscoveryOutcome("DIRECT_URL_REQUIRED" if value.kind == "NAME" else status)
        fallback = super().discover(value)
        requirement = "API_REQUIRED" if status == "NOT_CONFIGURED" else status
        for candidate in fallback.candidates:
            candidate.connector_requirement = requirement
            candidate.data_collection_status = "DATA_COLLECTION_REQUIRED"
            candidate.profile_data = {
                **candidate.profile_data,
                "meta_connector_status": status,
                "meta_connector_message": message,
            }
        return DiscoveryOutcome(requirement, fallback.candidates, [message])


class InstagramMetaConnector(_MetaConnector):
    def __init__(
        self,
        meta_client: MetaApiClient | None = None,
        config: CreatorDiscoveryConfig | None = None,
    ) -> None:
        super().__init__(DiscoveryPlatform.INSTAGRAM, meta_client, config)

    def discover(self, value: NormalizedDiscoveryInput) -> DiscoveryOutcome:
        if value.kind == "NAME":
            return DiscoveryOutcome("DIRECT_URL_REQUIRED")
        if value.kind != "PROFILE_URL" or value.platform is not self.platform or not value.url or not value.username:
            return DiscoveryOutcome("DIRECT_URL_REQUIRED")
        validation = self._platform_validation()
        if validation.status != "READY":
            return self._identity_fallback(value, validation.status, validation.message)
        try:
            raw = self.meta.get_instagram_profile(value.username)
            return DiscoveryOutcome("FOUND", [self._candidate(value.url, raw)])
        except MetaApiError as exc:
            return self._identity_fallback(value, exc.status, exc.safe_message)

    def collect_recent(self, candidate: DiscoveredCandidate, limit: int) -> list[DiscoveredContent]:
        validation = self._platform_validation()
        if validation.status != "READY" or not candidate.username:
            return []
        media = self.meta.get_instagram_media(candidate.username, limit)
        retrieved_at = datetime.now(UTC).isoformat()
        results: list[DiscoveredContent] = []
        for item in media[:limit]:
            media_id = str(item.get("id") or "") or None
            url = item.get("permalink") or (
                f"https://www.instagram.com/{candidate.username}/" if candidate.username else candidate.profile_url
            )
            caption = item.get("caption") or None
            results.append(DiscoveredContent(
                platform=self.platform,
                content_url=str(url),
                platform_content_id=media_id,
                published_at=_parse_datetime(item.get("timestamp")),
                caption=caption,
                content_type=str(item.get("media_product_type") or item.get("media_type") or "UNKNOWN"),
                likes=_integer(item.get("like_count")),
                comments=_integer(item.get("comments_count")),
                hashtags=sorted(set(re.findall(r"#([\w\u0600-\u06ff]+)", caption or ""))),
                metadata={
                    key: item[key] for key in ("media_type", "media_product_type", "media_url", "thumbnail_url")
                    if item.get(key) is not None
                },
                source=META_API_SOURCE,
                provenance=[{
                    "source": META_API_SOURCE,
                    "platform": "instagram",
                    "api_object_id": media_id,
                    "source_url": str(url),
                    "retrieved_at": retrieved_at,
                    "fields": sorted(item),
                }],
            ))
        return results

    def _candidate(self, profile_url: str, item: dict[str, Any]) -> DiscoveredCandidate:
        username = item.get("username")
        canonical = f"https://www.instagram.com/{username}" if username else profile_url
        retrieved_at = datetime.now(UTC).isoformat()
        candidate = DiscoveredCandidate(
            platform=self.platform,
            profile_url=normalize_profile_url(canonical)[1],
            display_name=item.get("name") or username,
            username=username,
            public_bio=item.get("biography") or None,
            public_avatar_url=item.get("profile_picture_url") or None,
            followers=_integer(item.get("followers_count")),
            following=_integer(item.get("follows_count")),
            content_count=_integer(item.get("media_count")),
            discovery_source=META_API_SOURCE,
            source_id=str(item.get("id") or "") or None,
            website=item.get("website") or None,
            profile_data={
                "meta_api_object_id": str(item.get("id") or "") or None,
                "website": item.get("website") or None,
                "meta_fields": sorted(item),
            },
            provenance=[{
                "source": META_API_SOURCE,
                "platform": "instagram",
                "api_object_id": str(item.get("id") or "") or None,
                "source_url": normalize_profile_url(canonical)[1],
                "retrieved_at": retrieved_at,
                "fields": sorted(item),
            }],
            connector_requirement="NONE",
        )
        candidate.data_completeness = data_completeness(candidate)
        candidate.data_collection_status = collection_status(candidate.data_completeness)
        return candidate


class FacebookMetaConnector(_MetaConnector):
    def __init__(
        self,
        meta_client: MetaApiClient | None = None,
        config: CreatorDiscoveryConfig | None = None,
    ) -> None:
        super().__init__(DiscoveryPlatform.FACEBOOK, meta_client, config)

    def discover(self, value: NormalizedDiscoveryInput) -> DiscoveryOutcome:
        if value.kind == "NAME":
            return DiscoveryOutcome("DIRECT_URL_REQUIRED")
        if value.kind != "PROFILE_URL" or value.platform is not self.platform or not value.url or not value.username:
            return DiscoveryOutcome("DIRECT_URL_REQUIRED")
        validation = self._platform_validation()
        if validation.status != "READY":
            return self._identity_fallback(value, validation.status, validation.message)
        try:
            raw = self.meta.get_facebook_page(value.username)
            return DiscoveryOutcome("FOUND", [self._candidate(value.url, raw)])
        except MetaApiError as exc:
            return self._identity_fallback(value, exc.status, exc.safe_message)

    def collect_recent(self, candidate: DiscoveredCandidate, limit: int) -> list[DiscoveredContent]:
        validation = self._platform_validation()
        if validation.status != "READY" or not candidate.source_id:
            return []
        posts = self.meta.get_facebook_posts(candidate.source_id, limit)
        retrieved_at = datetime.now(UTC).isoformat()
        results: list[DiscoveredContent] = []
        for item in posts[:limit]:
            post_id = str(item.get("id") or "") or None
            url = item.get("permalink_url") or f"https://www.facebook.com/{post_id}"
            message = item.get("message") or None
            attachments = _data_items(item.get("attachments"))
            attachment_type = next((entry.get("type") for entry in attachments if entry.get("type")), None)
            results.append(DiscoveredContent(
                platform=self.platform,
                content_url=str(url),
                platform_content_id=post_id,
                published_at=_parse_datetime(item.get("created_time")),
                caption=message,
                content_type=str(attachment_type or "POST").upper(),
                likes=_summary_count(item.get("likes")),
                comments=_summary_count(item.get("comments")),
                shares=_integer((item.get("shares") or {}).get("count")) if isinstance(item.get("shares"), dict) else None,
                hashtags=sorted(set(re.findall(r"#([\w\u0600-\u06ff]+)", message or ""))),
                metadata={
                    "full_picture": item.get("full_picture"),
                    "attachments": attachments,
                },
                source=META_API_SOURCE,
                provenance=[{
                    "source": META_API_SOURCE,
                    "platform": "facebook",
                    "api_object_id": post_id,
                    "source_url": str(url),
                    "retrieved_at": retrieved_at,
                    "fields": sorted(item),
                }],
            ))
        return results

    def _candidate(self, profile_url: str, item: dict[str, Any]) -> DiscoveredCandidate:
        username = item.get("username")
        canonical = item.get("link") or (f"https://www.facebook.com/{username}" if username else profile_url)
        try:
            canonical = normalize_profile_url(str(canonical))[1]
        except (ValueError, TypeError):
            canonical = profile_url
        picture = item.get("picture") or {}
        if isinstance(picture, dict):
            picture = (picture.get("data") or {}).get("url")
        retrieved_at = datetime.now(UTC).isoformat()
        candidate = DiscoveredCandidate(
            platform=self.platform,
            profile_url=str(canonical),
            display_name=item.get("name") or username,
            username=username,
            public_bio=item.get("about") or item.get("description") or None,
            public_avatar_url=picture if isinstance(picture, str) else None,
            followers=_integer(item.get("followers_count") if item.get("followers_count") is not None else item.get("fan_count")),
            content_count=None,
            verified=(str(item.get("verification_status") or "").casefold() not in {"", "not_verified"}),
            discovery_source=META_API_SOURCE,
            source_id=str(item.get("id") or "") or None,
            profile_data={
                "meta_api_object_id": str(item.get("id") or "") or None,
                "fan_count": _integer(item.get("fan_count")),
                "description": item.get("description") or None,
                "meta_fields": sorted(item),
            },
            provenance=[{
                "source": META_API_SOURCE,
                "platform": "facebook",
                "api_object_id": str(item.get("id") or "") or None,
                "source_url": str(canonical),
                "retrieved_at": retrieved_at,
                "fields": sorted(item),
            }],
            connector_requirement="NONE",
        )
        candidate.data_completeness = data_completeness(candidate)
        candidate.data_collection_status = collection_status(candidate.data_completeness)
        return candidate


# Backwards-compatible names used by existing imports.
InstagramConnector = InstagramMetaConnector
FacebookConnector = FacebookMetaConnector


class TikTokConnector(DirectURLConnector):
    def __init__(self, config: CreatorDiscoveryConfig | None = None) -> None:
        super().__init__(DiscoveryPlatform.TIKTOK, config)


class SnapchatConnector(DirectURLConnector):
    def __init__(self, config: CreatorDiscoveryConfig | None = None) -> None:
        super().__init__(DiscoveryPlatform.SNAPCHAT, config)


class LinkedInConnector(DirectURLConnector):
    def __init__(self, config: CreatorDiscoveryConfig | None = None) -> None:
        super().__init__(DiscoveryPlatform.LINKEDIN, config)


class XConnector(DirectURLConnector):
    def __init__(self, config: CreatorDiscoveryConfig | None = None) -> None:
        super().__init__(DiscoveryPlatform.X, config)


class CreatorDiscoveryConnectorRegistry:
    def __init__(self, connectors: list[PlatformDiscoveryConnector] | None = None) -> None:
        meta = MetaApiClient()
        values = connectors or [
            YouTubeConnector(), FacebookMetaConnector(meta), InstagramMetaConnector(meta), TikTokConnector(),
            SnapchatConnector(), LinkedInConnector(), XConnector(),
        ]
        self._connectors = {connector.platform: connector for connector in values}

    def get(self, platform: DiscoveryPlatform | str) -> PlatformDiscoveryConnector:
        return self._connectors[DiscoveryPlatform(platform)]

    def capabilities(self) -> list[dict[str, Any]]:
        return [self._connectors[platform].capability() for platform in DiscoveryPlatform]

    def meta_status(self, *, force: bool = False) -> dict[str, Any]:
        connector = self._connectors.get(DiscoveryPlatform.INSTAGRAM)
        if isinstance(connector, _MetaConnector):
            return connector.meta.validate(force=force).public_payload()
        return MetaApiClient().validate(force=force).public_payload()


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _data_items(value: Any) -> list[dict[str, Any]]:
    data = value.get("data") if isinstance(value, dict) else None
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _summary_count(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    summary = value.get("summary")
    return _integer(summary.get("total_count")) if isinstance(summary, dict) else None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso_duration_seconds(value: Any) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", str(value))
    if not match:
        return None
    days, hours, minutes, seconds = match.groups()
    return int(days or 0) * 86400 + int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)
