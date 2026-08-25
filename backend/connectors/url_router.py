"""Route supported platform URLs without making network requests."""

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlparse

from backend.core.enums import Platform
from backend.core.exceptions import InvalidAccountError


class PlatformURLKind(StrEnum):
    PROFILE = "profile"
    CONTENT = "content"


@dataclass(frozen=True)
class PlatformURLRoute:
    platform: Platform
    kind: PlatformURLKind
    reference: str


_HOSTS = {
    "instagram.com": Platform.INSTAGRAM,
    "tiktok.com": Platform.TIKTOK,
    "youtube.com": Platform.YOUTUBE,
    "youtu.be": Platform.YOUTUBE,
    "facebook.com": Platform.FACEBOOK,
    "fb.watch": Platform.FACEBOOK,
    "t.me": Platform.TELEGRAM,
    "telegram.me": Platform.TELEGRAM,
    "x.com": Platform.X,
    "twitter.com": Platform.X,
}


def route_platform_url(url: str) -> PlatformURLRoute:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidAccountError("A valid http(s) platform URL is required")
    hostname = parsed.hostname.casefold().removeprefix("www.")
    platform = next(
        (
            value
            for host, value in _HOSTS.items()
            if hostname == host or hostname.endswith(f".{host}")
        ),
        None,
    )
    if platform is None:
        raise InvalidAccountError("The URL host is not a supported platform")

    parts = [part for part in parsed.path.split("/") if part]
    kind = _classify(platform, hostname, parts, parse_qs(parsed.query))
    reference = parts[-1].lstrip("@") if parts else hostname
    return PlatformURLRoute(platform=platform, kind=kind, reference=reference)


def _classify(
    platform: Platform,
    hostname: str,
    parts: list[str],
    query: dict[str, list[str]],
) -> PlatformURLKind:
    if hostname in {"youtu.be", "fb.watch"}:
        return PlatformURLKind.CONTENT
    if platform is Platform.INSTAGRAM and parts[:1] in [["p"], ["reel"], ["tv"]]:
        return PlatformURLKind.CONTENT
    if platform is Platform.TIKTOK and "video" in parts:
        return PlatformURLKind.CONTENT
    if platform is Platform.YOUTUBE and (
        parts[:1] in [["shorts"], ["live"]] or "v" in query
    ):
        return PlatformURLKind.CONTENT
    if platform is Platform.FACEBOOK and any(
        marker in parts for marker in ("posts", "videos", "reel", "watch")
    ):
        return PlatformURLKind.CONTENT
    if platform is Platform.TELEGRAM and len(parts) >= 2:
        return PlatformURLKind.CONTENT
    if platform is Platform.X and "status" in parts:
        return PlatformURLKind.CONTENT
    return PlatformURLKind.PROFILE
