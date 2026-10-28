"""Strict public social URL validation and canonicalization."""

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.social_inventory.exceptions import SocialInventoryError

ALLOWED_SOCIAL_HOSTS = {
    "instagram.com", "www.instagram.com", "tiktok.com", "www.tiktok.com",
    "facebook.com", "www.facebook.com", "youtube.com", "www.youtube.com", "youtu.be",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com", "linkedin.com", "www.linkedin.com",
}
HOST_PLATFORM = {
    "instagram.com": "instagram", "tiktok.com": "tiktok", "facebook.com": "facebook",
    "youtube.com": "youtube", "youtu.be": "youtube", "x.com": "x", "twitter.com": "x",
    "linkedin.com": "linkedin",
}


def _error(message: str) -> SocialInventoryError:
    return SocialInventoryError("SOCIAL_INVALID_URL", message, status_code=422)


def validate_social_url(value: str, *, resolve_dns: bool = False) -> tuple[str, str]:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise _error("Malformed social URL.") from exc
    if parsed.scheme.lower() != "https":
        raise _error("Only https social URLs are accepted.")
    if parsed.username or parsed.password or port not in (None, 443):
        raise _error("Credentials and non-standard ports are not allowed.")
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise _error("Direct IP addresses are not allowed.")
    if host not in ALLOWED_SOCIAL_HOSTS:
        raise _error("The URL host is not an allowed social platform.")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise _error("The social host could not be resolved.") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise _error("The URL resolves to a non-public network.")
    base_host = host.removeprefix("www.")
    platform = HOST_PLATFORM[base_host]
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    path = "/" + "/".join(part for part in parsed.path.split("/") if part)
    if path != "/":
        path += "/"
    canonical_host = "x.com" if base_host == "twitter.com" else base_host
    canonical = urlunsplit(("https", canonical_host, path, urlencode(query), ""))
    return canonical, platform


def validate_redirect(original_platform: str, location: str) -> str:
    canonical, platform = validate_social_url(location)
    if platform != original_platform:
        raise _error("Provider redirect left the selected platform.")
    return canonical
