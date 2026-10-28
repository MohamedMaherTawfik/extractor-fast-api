"""Safe media URL validation, SSRF prevention, and temporary media acquisition."""

from __future__ import annotations

import ipaddress
import logging
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.core.paths import paths

logger = logging.getLogger(__name__)

# Disallowed IP networks for SSRF prevention
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(slots=True)
class MediaValidationResult:
    is_accessible: bool
    status_code: int | None
    content_type: str | None
    content_length: int | None
    is_expired: bool
    error_message: str | None = None


def is_safe_url(url: str) -> tuple[bool, str | None]:
    """Verify URL scheme and ensure destination IP does not resolve to private/internal networks."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"Unsupported URL scheme: {parsed.scheme}"
        hostname = parsed.hostname
        if not hostname:
            return False, "URL contains no hostname"
        if hostname.lower() in {"localhost", "metadata.google.internal"}:
            return False, "Access to localhost or metadata services is blocked"

        # Resolve hostname to check for internal/private addresses
        ip_addresses = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in ip_addresses:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for network in BLOCKED_NETWORKS:
                if ip_obj in network:
                    return False, f"URL resolves to restricted network: {ip_str}"
        return True, None
    except Exception as exc:
        return False, f"URL validation failed: {exc}"


def validate_media_url(url: str, timeout: float = 15.0) -> MediaValidationResult:
    """Check if media URL is currently accessible and not expired."""
    is_safe, err = is_safe_url(url)
    if not is_safe:
        return MediaValidationResult(
            is_accessible=False,
            status_code=None,
            content_type=None,
            content_length=None,
            is_expired=False,
            error_message=err,
        )

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            # First try HEAD request to check availability without downloading payload
            response = client.head(url)
            if response.status_code in {403, 410}:
                return MediaValidationResult(
                    is_accessible=False,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    content_length=None,
                    is_expired=True,
                    error_message=f"Media URL has expired or is forbidden (HTTP {response.status_code})",
                )
            if response.status_code == 405 or response.status_code >= 400:
                # Some CDNs reject HEAD; try GET with Range header for 1 byte
                response = client.get(url, headers={"Range": "bytes=0-0"})

            content_length = response.headers.get("content-length")
            cl_int = int(content_length) if content_length and content_length.isdigit() else None
            content_type = response.headers.get("content-type")

            if response.is_success or response.status_code == 206:
                return MediaValidationResult(
                    is_accessible=True,
                    status_code=response.status_code,
                    content_type=content_type,
                    content_length=cl_int,
                    is_expired=False,
                )
            else:
                is_expired = response.status_code in {403, 404, 410}
                return MediaValidationResult(
                    is_accessible=False,
                    status_code=response.status_code,
                    content_type=content_type,
                    content_length=cl_int,
                    is_expired=is_expired,
                    error_message=f"HTTP {response.status_code} accessing media URL",
                )
    except httpx.TimeoutException:
        return MediaValidationResult(
            is_accessible=False,
            status_code=None,
            content_type=None,
            content_length=None,
            is_expired=False,
            error_message="Connection timed out while validating media URL",
        )
    except Exception as exc:
        return MediaValidationResult(
            is_accessible=False,
            status_code=None,
            content_type=None,
            content_length=None,
            is_expired=False,
            error_message=f"Network error validating media URL: {exc}",
        )


def download_media_to_temp(
    url: str,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    file_prefix: str = "media_",
) -> Path:
    """Safely stream media URL into a temporary file with byte limit enforcement."""
    is_safe, err = is_safe_url(url)
    if not is_safe:
        raise ValueError(f"Security validation rejected URL: {err}")

    temp_dir = paths.data / "temp_media"
    temp_dir.mkdir(parents=True, exist_ok=True)

    fd, raw_path = tempfile.mkstemp(prefix=file_prefix, suffix=".mp4", dir=str(temp_dir))
    target_path = Path(raw_path)

    try:
        with os.fdopen(fd, "wb") as f_out:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    if not response.is_success:
                        raise RuntimeError(
                            f"Failed to download media: HTTP {response.status_code}"
                        )
                    bytes_downloaded = 0
                    for chunk in response.iter_bytes(chunk_size=65536):
                        bytes_downloaded += len(chunk)
                        if bytes_downloaded > max_bytes:
                            raise ValueError(
                                f"Media exceeds maximum allowed size ({max_bytes} bytes)"
                            )
                        f_out.write(chunk)
        return target_path
    except Exception:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise


def cleanup_temp_file(path: Path | str | None) -> None:
    """Safely remove a temporary file if it exists."""
    if not path:
        return
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            p.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to remove temp file %s: %s", path, exc)
