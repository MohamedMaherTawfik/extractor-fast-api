"""Deterministic name, URL, username, and platform normalization."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from backend.core.exceptions import NormalizationError
from backend.schemas.creator_discovery import DiscoveryPlatform


HOST_PLATFORMS = {
    "youtube.com": DiscoveryPlatform.YOUTUBE,
    "youtu.be": DiscoveryPlatform.YOUTUBE,
    "facebook.com": DiscoveryPlatform.FACEBOOK,
    "fb.com": DiscoveryPlatform.FACEBOOK,
    "instagram.com": DiscoveryPlatform.INSTAGRAM,
    "tiktok.com": DiscoveryPlatform.TIKTOK,
    "snapchat.com": DiscoveryPlatform.SNAPCHAT,
    "linkedin.com": DiscoveryPlatform.LINKEDIN,
    "x.com": DiscoveryPlatform.X,
    "twitter.com": DiscoveryPlatform.X,
}

_CONTENT_MARKERS = {
    DiscoveryPlatform.YOUTUBE: {"watch", "shorts", "live"},
    DiscoveryPlatform.FACEBOOK: {"posts", "videos", "reel", "watch"},
    DiscoveryPlatform.INSTAGRAM: {"p", "reel", "tv"},
    DiscoveryPlatform.TIKTOK: {"video"},
    DiscoveryPlatform.X: {"status"},
}


@dataclass(frozen=True, slots=True)
class NormalizedDiscoveryInput:
    original: str
    kind: str
    normalized: str
    platform: DiscoveryPlatform | None = None
    username: str | None = None
    url: str | None = None


def normalize_creator_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def normalize_username(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = unicodedata.normalize("NFKC", value).strip().lstrip("@").rstrip("/")
    return cleaned.casefold() or None


def detect_platform(value: str) -> DiscoveryPlatform | None:
    candidate = value.strip()
    if not candidate.casefold().startswith(("http://", "https://")):
        return None
    hostname = (urlsplit(candidate).hostname or "").casefold().removeprefix("www.")
    return next(
        (platform for host, platform in HOST_PLATFORMS.items() if hostname == host or hostname.endswith(f".{host}")),
        None,
    )


def normalize_profile_url(value: str) -> tuple[DiscoveryPlatform, str, str | None]:
    candidate = value.strip()
    if not candidate.casefold().startswith(("http://", "https://")):
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    hostname = (parsed.hostname or "").casefold().removeprefix("www.")
    platform = next(
        (item for host, item in HOST_PLATFORMS.items() if hostname == host or hostname.endswith(f".{host}")),
        None,
    )
    if platform is None:
        raise NormalizationError("The URL host is not a supported creator platform")
    if hostname == "youtu.be":
        raise NormalizationError("A YouTube channel URL is required, not a video URL")
    parts = [part for part in parsed.path.split("/") if part]
    if any(marker in parts for marker in _CONTENT_MARKERS.get(platform, set())):
        raise NormalizationError("A profile/account URL is required, not a content URL")
    username = _username_from_parts(platform, parts)
    canonical_host = {
        DiscoveryPlatform.YOUTUBE: "www.youtube.com",
        DiscoveryPlatform.FACEBOOK: "www.facebook.com",
        DiscoveryPlatform.INSTAGRAM: "www.instagram.com",
        DiscoveryPlatform.TIKTOK: "www.tiktok.com",
        DiscoveryPlatform.SNAPCHAT: "www.snapchat.com",
        DiscoveryPlatform.LINKEDIN: "www.linkedin.com",
        DiscoveryPlatform.X: "x.com",
    }[platform]
    path = "/" + "/".join(parts) if parts else ""
    canonical = urlunsplit(("https", canonical_host, path, "", "")).rstrip("/")
    return platform, canonical, normalize_username(username)


def normalize_discovery_input(value: str) -> NormalizedDiscoveryInput:
    original = value.strip()
    if not original:
        raise NormalizationError("Creator input cannot be empty")
    if original.casefold().startswith(("http://", "https://", "www.")):
        platform, url, username = normalize_profile_url(original)
        return NormalizedDiscoveryInput(original, "PROFILE_URL", url, platform, username, url)
    normalized = normalize_creator_name(original)
    if not normalized:
        raise NormalizationError("Creator name contains no searchable characters")
    return NormalizedDiscoveryInput(original, "NAME", normalized)


def _username_from_parts(platform: DiscoveryPlatform, parts: list[str]) -> str | None:
    if not parts:
        return None
    if platform is DiscoveryPlatform.YOUTUBE:
        if parts[0].startswith("@"):
            return parts[0][1:]
        if parts[0].casefold() in {"channel", "c", "user"} and len(parts) > 1:
            return parts[1]
    if platform is DiscoveryPlatform.SNAPCHAT and parts[0].casefold() in {"add", "p"}:
        return parts[1] if len(parts) > 1 else None
    if platform is DiscoveryPlatform.LINKEDIN and parts[0].casefold() in {"in", "company", "school"}:
        return parts[1] if len(parts) > 1 else None
    return parts[0].lstrip("@")
