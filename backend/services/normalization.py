"""Pure platform identity normalization with no network access."""

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from backend.core.enums import Platform
from backend.core.exceptions import NormalizationError


PLATFORM_ALIASES = {
    "instagram": Platform.INSTAGRAM,
    "ig": Platform.INSTAGRAM,
    "tiktok": Platform.TIKTOK,
    "tik tok": Platform.TIKTOK,
    "youtube": Platform.YOUTUBE,
    "yt": Platform.YOUTUBE,
    "facebook": Platform.FACEBOOK,
    "fb": Platform.FACEBOOK,
    "telegram": Platform.TELEGRAM,
    "tg": Platform.TELEGRAM,
    "x": Platform.X,
    "twitter": Platform.X,
    "website": Platform.WEBSITE,
    "web": Platform.WEBSITE,
    "other": Platform.OTHER,
}

HOST_PLATFORMS = {
    "instagram.com": Platform.INSTAGRAM,
    "tiktok.com": Platform.TIKTOK,
    "youtube.com": Platform.YOUTUBE,
    "youtu.be": Platform.YOUTUBE,
    "facebook.com": Platform.FACEBOOK,
    "fb.com": Platform.FACEBOOK,
    "t.me": Platform.TELEGRAM,
    "telegram.me": Platform.TELEGRAM,
    "x.com": Platform.X,
    "twitter.com": Platform.X,
}


@dataclass(frozen=True, slots=True)
class NormalizedAccount:
    platform: Platform
    username: str | None
    profile_url: str | None
    platform_user_id: str | None


class AccountNormalizer:
    def normalize_platform(self, value: Platform | str | None) -> Platform | None:
        if value is None or value == "":
            return None
        if isinstance(value, Platform):
            return value
        normalized = " ".join(str(value).strip().casefold().split())
        try:
            return PLATFORM_ALIASES[normalized]
        except KeyError as exc:
            raise NormalizationError(f"Unsupported platform: {value}") from exc

    def normalize_account(
        self,
        *,
        platform: Platform | str | None,
        username: str | None = None,
        profile_url: str | None = None,
        platform_user_id: str | None = None,
    ) -> NormalizedAccount:
        normalized_platform = self.normalize_platform(platform)
        username_value = self._clean_optional(username)
        url_value = self._clean_optional(profile_url)
        platform_id = self._clean_optional(platform_user_id)

        if username_value and self._looks_like_url(username_value):
            url_value = username_value
            username_value = None

        parsed_url, inferred_platform = self._parse_url(url_value)
        if normalized_platform and inferred_platform and normalized_platform != inferred_platform:
            raise NormalizationError(
                "Platform does not match the supplied profile URL"
            )
        normalized_platform = normalized_platform or inferred_platform
        if normalized_platform is None:
            raise NormalizationError("Platform could not be determined")

        extracted_username, extracted_platform_id = self._extract_identity(
            normalized_platform,
            parsed_url,
        )
        username_value = self._normalize_username(
            username_value or extracted_username
        )
        platform_id = platform_id or extracted_platform_id

        if not (username_value or platform_id or parsed_url):
            raise NormalizationError(
                "username, platform_user_id, or profile_url is required"
            )

        canonical_url = self._canonical_url(
            normalized_platform,
            username_value,
            parsed_url,
        )
        return NormalizedAccount(
            platform=normalized_platform,
            username=username_value,
            profile_url=canonical_url,
            platform_user_id=platform_id,
        )

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        lowered = value.casefold()
        return (
            lowered.startswith(("http://", "https://", "www."))
            or "/" in value
            and "." in value.split("/", 1)[0]
        )

    def _parse_url(
        self,
        value: str | None,
    ) -> tuple[tuple[str, str, str] | None, Platform | None]:
        if value is None:
            return None, None
        candidate = value
        if not candidate.casefold().startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        parsed = urlparse(candidate)
        if not parsed.netloc:
            raise NormalizationError("Invalid profile URL")
        host = parsed.netloc.casefold().split(":", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        path = "/" + unquote(parsed.path).strip("/")
        if path == "/":
            path = ""
        return ("https", host, path), HOST_PLATFORMS.get(host)

    @staticmethod
    def _extract_identity(
        platform: Platform,
        parsed_url: tuple[str, str, str] | None,
    ) -> tuple[str | None, str | None]:
        if parsed_url is None:
            return None, None
        segments = [segment for segment in parsed_url[2].split("/") if segment]
        if not segments:
            return None, None
        if platform is Platform.YOUTUBE and segments[0].casefold() == "channel":
            return None, segments[1] if len(segments) > 1 else None
        if platform is Platform.YOUTUBE and segments[0].casefold() in {"user", "c"}:
            return segments[1] if len(segments) > 1 else None, None
        return segments[0].lstrip("@"), None

    @staticmethod
    def _normalize_username(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lstrip("@").rstrip("/").strip()
        return normalized.casefold() or None

    @staticmethod
    def _canonical_url(
        platform: Platform,
        username: str | None,
        parsed_url: tuple[str, str, str] | None,
    ) -> str | None:
        if username:
            templates = {
                Platform.INSTAGRAM: "https://www.instagram.com/{username}",
                Platform.TIKTOK: "https://www.tiktok.com/@{username}",
                Platform.YOUTUBE: "https://www.youtube.com/@{username}",
                Platform.FACEBOOK: "https://www.facebook.com/{username}",
                Platform.TELEGRAM: "https://t.me/{username}",
                Platform.X: "https://x.com/{username}",
            }
            template = templates.get(platform)
            if template:
                return template.format(username=username)
        if parsed_url:
            scheme, host, path = parsed_url
            return f"{scheme}://{host}{path}".rstrip("/")
        return None
