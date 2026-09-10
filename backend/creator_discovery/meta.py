"""Shared, backend-only Meta Graph API transport and connection validation."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from backend.core.config import Settings, get_settings


META_API_SOURCE = "meta_api"
_RATE_LIMIT_CODES = {4, 17, 32, 341, 613}
_TRANSIENT_CODES = {1, 2, *_RATE_LIMIT_CODES}
_TOKEN_EXPIRED_SUBCODES = {463}
_TOKEN_INVALIDATED_SUBCODES = {458, 459, 460, 464, 467}
_PERMISSION_CODES = {10, 200, 294}
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")


class MetaApiError(RuntimeError):
    """Sanitized Meta failure which never contains credentials or raw payloads."""

    def __init__(
        self,
        status: str,
        message: str,
        *,
        http_status: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.safe_message = message
        self.http_status = http_status
        self.code = code
        self.subcode = subcode
        self.retryable = retryable


@dataclass(slots=True)
class MetaPlatformValidation:
    status: str
    message: str
    account_configured: bool
    required_permissions: list[str] = field(default_factory=list)
    missing_permissions: list[str] = field(default_factory=list)
    account_id: str | None = None
    account_name: str | None = None


@dataclass(slots=True)
class MetaConnectionValidation:
    app_id_configured: bool
    app_secret_configured: bool
    access_token_configured: bool
    token_hint: str | None
    graph_api_version: str
    token_status: str
    token_message: str
    token_expires_at: str | None
    granted_permissions: list[str]
    last_validation: str
    instagram: MetaPlatformValidation
    facebook: MetaPlatformValidation

    def public_payload(self) -> dict[str, Any]:
        """Return only non-secret configuration and validation information."""
        payload = asdict(self)
        payload["configured"] = all((
            self.app_id_configured,
            self.app_secret_configured,
            self.access_token_configured,
        ))
        return payload


class MetaApiClient:
    """Official Graph API client shared by Instagram and Facebook connectors."""

    instagram_permissions = ["instagram_basic", "pages_read_engagement", "pages_show_list"]
    facebook_permissions = ["pages_read_engagement", "pages_show_list"]

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.app_id = (self.settings.meta_app_id or "").strip()
        self.app_secret = (self.settings.meta_app_secret or "").strip()
        self.access_token = (self.settings.meta_access_token or "").strip()
        self.api_version = self.settings.meta_graph_api_version
        self.facebook_page_id = (self.settings.meta_facebook_page_id or "").strip()
        self.instagram_account_id = (self.settings.meta_instagram_account_id or "").strip()
        self._transport = transport
        self._sleeper = sleeper
        self._validation: MetaConnectionValidation | None = None

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.access_token)

    @property
    def token_hint(self) -> str | None:
        return f"****{self.access_token[-4:]}" if self.access_token else None

    def validate(self, *, force: bool = False) -> MetaConnectionValidation:
        if self._validation is not None and not force:
            return self._validation
        checked_at = datetime.now(UTC).isoformat()
        missing = MetaPlatformValidation(
            status="NOT_CONFIGURED",
            message="Meta App ID, App Secret, and Access Token are required.",
            account_configured=False,
        )
        if not self.configured:
            self._validation = MetaConnectionValidation(
                app_id_configured=bool(self.app_id),
                app_secret_configured=bool(self.app_secret),
                access_token_configured=bool(self.access_token),
                token_hint=self.token_hint,
                graph_api_version=self.api_version,
                token_status="NOT_CONFIGURED",
                token_message="Meta credentials are not fully configured.",
                token_expires_at=None,
                granted_permissions=[],
                last_validation=checked_at,
                instagram=MetaPlatformValidation(**asdict(missing)),
                facebook=MetaPlatformValidation(**asdict(missing)),
            )
            return self._validation

        try:
            debug = self._debug_token()
            expires_at = _timestamp_iso(debug.get("expires_at"))
            if not debug.get("is_valid"):
                raise MetaApiError("TOKEN_INVALID", "Meta rejected the configured access token.")
            if str(debug.get("app_id") or "") != self.app_id:
                raise MetaApiError("TOKEN_INVALID", "The access token belongs to a different Meta app.")
            expiry = _integer(debug.get("expires_at"))
            if expiry and expiry <= int(time.time()):
                raise MetaApiError("TOKEN_EXPIRED", "The configured Meta access token has expired.")
            granted = sorted({str(value) for value in debug.get("scopes", []) if value})
            if not granted:
                granted = self._permissions()
            instagram = self._validate_instagram(granted)
            facebook = self._validate_facebook(granted)
            self._validation = MetaConnectionValidation(
                app_id_configured=True,
                app_secret_configured=True,
                access_token_configured=True,
                token_hint=self.token_hint,
                graph_api_version=self.api_version,
                token_status="READY",
                token_message="Access token validation succeeded.",
                token_expires_at=expires_at,
                granted_permissions=granted,
                last_validation=checked_at,
                instagram=instagram,
                facebook=facebook,
            )
        except MetaApiError as exc:
            platform = MetaPlatformValidation(
                status=exc.status,
                message=exc.safe_message,
                account_configured=False,
            )
            self._validation = MetaConnectionValidation(
                app_id_configured=True,
                app_secret_configured=True,
                access_token_configured=True,
                token_hint=self.token_hint,
                graph_api_version=self.api_version,
                token_status=exc.status,
                token_message=exc.safe_message,
                token_expires_at=None,
                granted_permissions=[],
                last_validation=checked_at,
                instagram=MetaPlatformValidation(**asdict(platform)),
                facebook=MetaPlatformValidation(**asdict(platform)),
            )
        return self._validation

    def get_instagram_profile(self, username: str) -> dict[str, Any]:
        username = _validated_identifier(username, "Instagram username")
        fields = (
            "id,username,name,biography,followers_count,follows_count,media_count,"
            "profile_picture_url,website"
        )
        if not self.instagram_account_id:
            raise MetaApiError("ACCOUNT_NOT_LINKED", "No Instagram professional account ID is configured.")
        own = self._request(self.instagram_account_id, {"fields": fields})
        if str(own.get("username") or "").casefold() == username.casefold():
            return own
        discovery_fields = f"business_discovery.username({username}){{{fields}}}"
        payload = self._request(self.instagram_account_id, {"fields": discovery_fields})
        result = payload.get("business_discovery")
        if not isinstance(result, dict):
            raise MetaApiError(
                "ACCOUNT_NOT_ACCESSIBLE",
                "The Instagram account is not accessible through Business Discovery.",
            )
        return result

    def get_instagram_media(self, username: str, limit: int) -> list[dict[str, Any]]:
        username = _validated_identifier(username, "Instagram username")
        limit = max(1, min(int(limit), 30))
        fields = (
            "id,caption,media_type,media_product_type,media_url,permalink,timestamp,"
            "thumbnail_url,like_count,comments_count"
        )
        profile = self.get_instagram_profile(username)
        if str(profile.get("id")) == self.instagram_account_id:
            payload = self._request(f"{self.instagram_account_id}/media", {"fields": fields, "limit": limit})
            return _data_list(payload)[:limit]
        discovery = f"business_discovery.username({username}){{media.limit({limit}){{{fields}}}}}"
        payload = self._request(self.instagram_account_id, {"fields": discovery})
        media = (payload.get("business_discovery") or {}).get("media") or {}
        return _data_list(media)[:limit]

    def get_facebook_page(self, identifier: str) -> dict[str, Any]:
        identifier = _validated_identifier(identifier, "Facebook Page identifier")
        fields = (
            "id,name,username,link,about,description,fan_count,followers_count,"
            "verification_status,picture.type(large){url}"
        )
        return self._request(identifier, {"fields": fields})

    def get_facebook_posts(self, page_id: str, limit: int) -> list[dict[str, Any]]:
        page_id = _validated_identifier(page_id, "Facebook Page identifier")
        limit = max(1, min(int(limit), 30))
        fields = (
            "id,message,created_time,permalink_url,full_picture,"
            "attachments{media,type,url},shares,likes.limit(0).summary(true),"
            "comments.limit(0).summary(true)"
        )
        try:
            payload = self._request(f"{page_id}/posts", {"fields": fields, "limit": limit})
        except MetaApiError as exc:
            if exc.status != "PERMISSION_MISSING":
                raise
            basic_fields = "id,message,created_time,permalink_url,full_picture,attachments{media,type,url}"
            payload = self._request(f"{page_id}/posts", {"fields": basic_fields, "limit": limit})
        return _data_list(payload)[:limit]

    def _validate_instagram(self, granted: list[str]) -> MetaPlatformValidation:
        missing = sorted(set(self.instagram_permissions) - set(granted))
        if missing:
            return MetaPlatformValidation(
                status="PERMISSION_MISSING",
                message="Required Instagram permissions are missing.",
                account_configured=bool(self.instagram_account_id),
                required_permissions=self.instagram_permissions,
                missing_permissions=missing,
            )
        if not self.instagram_account_id:
            return MetaPlatformValidation(
                status="ACCOUNT_NOT_LINKED",
                message="META_INSTAGRAM_ACCOUNT_ID is not configured.",
                account_configured=False,
                required_permissions=self.instagram_permissions,
            )
        try:
            account = self._request(self.instagram_account_id, {"fields": "id,username,name"})
            return MetaPlatformValidation(
                status="READY",
                message="Instagram professional account access validated.",
                account_configured=True,
                required_permissions=self.instagram_permissions,
                account_id=str(account.get("id") or self.instagram_account_id),
                account_name=account.get("username") or account.get("name"),
            )
        except MetaApiError as exc:
            return MetaPlatformValidation(
                status=exc.status if exc.status != "TOKEN_INVALID" else "ACCOUNT_NOT_LINKED",
                message=exc.safe_message,
                account_configured=True,
                required_permissions=self.instagram_permissions,
            )

    def _validate_facebook(self, granted: list[str]) -> MetaPlatformValidation:
        missing = sorted(set(self.facebook_permissions) - set(granted))
        if missing:
            return MetaPlatformValidation(
                status="PERMISSION_MISSING",
                message="Required Facebook Page permissions are missing.",
                account_configured=bool(self.facebook_page_id),
                required_permissions=self.facebook_permissions,
                missing_permissions=missing,
            )
        if not self.facebook_page_id:
            return MetaPlatformValidation(
                status="ACCOUNT_NOT_LINKED",
                message="META_FACEBOOK_PAGE_ID is not configured.",
                account_configured=False,
                required_permissions=self.facebook_permissions,
            )
        try:
            page = self.get_facebook_page(self.facebook_page_id)
            return MetaPlatformValidation(
                status="READY",
                message="Facebook Page access validated.",
                account_configured=True,
                required_permissions=self.facebook_permissions,
                account_id=str(page.get("id") or self.facebook_page_id),
                account_name=page.get("username") or page.get("name"),
            )
        except MetaApiError as exc:
            return MetaPlatformValidation(
                status=exc.status if exc.status != "TOKEN_INVALID" else "ACCOUNT_NOT_LINKED",
                message=exc.safe_message,
                account_configured=True,
                required_permissions=self.facebook_permissions,
            )

    def _debug_token(self) -> dict[str, Any]:
        app_access_token = f"{self.app_id}|{self.app_secret}"
        payload = self._request(
            "debug_token",
            {"input_token": self.access_token},
            access_token=app_access_token,
            include_proof=False,
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MetaApiError("TOKEN_INVALID", "Meta token validation returned an invalid response.")
        return data

    def _permissions(self) -> list[str]:
        try:
            payload = self._request("me/permissions", {})
        except MetaApiError:
            return []
        return sorted({
            str(item.get("permission"))
            for item in _data_list(payload)
            if item.get("status") == "granted" and item.get("permission")
        })

    def _request(
        self,
        path: str,
        params: dict[str, Any],
        *,
        access_token: str | None = None,
        include_proof: bool = True,
    ) -> dict[str, Any]:
        token = access_token or self.access_token
        if not token:
            raise MetaApiError("NOT_CONFIGURED", "A Meta access token is required.")
        request_params = dict(params)
        if include_proof and self.app_secret:
            request_params["appsecret_proof"] = hmac.new(
                self.app_secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256,
            ).hexdigest()
        url = f"https://graph.facebook.com/{self.api_version}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        for attempt in range(3):
            try:
                with httpx.Client(
                    timeout=15.0,
                    follow_redirects=False,
                    transport=self._transport,
                ) as client:
                    response = client.get(url, params=request_params, headers=headers)
            except httpx.TransportError:
                if attempt < 2:
                    self._sleeper(float(2**attempt))
                    continue
                raise MetaApiError(
                    "API_UNAVAILABLE", "The Meta API is temporarily unavailable.", retryable=True,
                ) from None
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = payload.get("error") if isinstance(payload, dict) else None
            code = _integer(error.get("code")) if isinstance(error, dict) else None
            subcode = _integer(error.get("error_subcode")) if isinstance(error, dict) else None
            retryable = response.status_code == 429 or code in _TRANSIENT_CODES
            if response.status_code < 400 and not error:
                if not isinstance(payload, dict):
                    raise MetaApiError("API_UNAVAILABLE", "Meta returned an invalid response.")
                return payload
            if retryable and attempt < 2:
                delay = _retry_delay(response, attempt)
                self._sleeper(delay)
                continue
            status, message = _classify_error(response.status_code, code, subcode, error)
            raise MetaApiError(
                status,
                message,
                http_status=response.status_code,
                code=code,
                subcode=subcode,
                retryable=retryable,
            )
        raise MetaApiError("API_UNAVAILABLE", "The Meta API is temporarily unavailable.")


def _classify_error(
    http_status: int,
    code: int | None,
    subcode: int | None,
    error: Any,
) -> tuple[str, str]:
    message_text = str(error.get("message") or "").casefold() if isinstance(error, dict) else ""
    if http_status == 429 or code in _RATE_LIMIT_CODES:
        return "RATE_LIMITED", "Meta rate-limited the request; retry after the indicated cooldown."
    if subcode in _TOKEN_EXPIRED_SUBCODES or "token" in message_text and "expired" in message_text:
        return "TOKEN_EXPIRED", "The configured Meta access token has expired."
    if code == 190 or subcode in _TOKEN_INVALIDATED_SUBCODES:
        return "TOKEN_INVALID", "Meta rejected the configured access token."
    if code in _PERMISSION_CODES or http_status == 403:
        return "PERMISSION_MISSING", "The Meta app or token lacks permission for this request."
    if http_status == 404 or code == 100:
        return "ACCOUNT_NOT_ACCESSIBLE", "The requested Meta account is unavailable or not accessible to this app."
    if http_status >= 500 or code in _TRANSIENT_CODES:
        return "API_UNAVAILABLE", "The Meta API is temporarily unavailable."
    return "API_UNAVAILABLE", "The Meta API request could not be completed."


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        value = float(response.headers.get("Retry-After", ""))
        return max(0.0, min(value, 30.0))
    except ValueError:
        return float(2**attempt)


def _validated_identifier(value: str, label: str) -> str:
    cleaned = str(value or "").strip().lstrip("@")
    if not cleaned or not _SAFE_IDENTIFIER.fullmatch(cleaned):
        raise MetaApiError("ACCOUNT_NOT_ACCESSIBLE", f"{label} is invalid.")
    return cleaned


def _data_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _timestamp_iso(value: Any) -> str | None:
    timestamp = _integer(value)
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    except (OSError, OverflowError, ValueError):
        return None
