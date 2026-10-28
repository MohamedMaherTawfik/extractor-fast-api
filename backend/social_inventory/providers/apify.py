"""Async Apify REST adapter with bounded retries and secret-safe errors."""

import asyncio
import logging
from typing import Any

import httpx

from backend.core.config import Settings, get_settings
from backend.social_inventory.exceptions import SocialInventoryError
from backend.social_inventory.providers.actor_inputs import BUILDERS
from backend.social_inventory.schemas import ProviderCapabilities, ProviderItemsPage, ProviderRun, StartProviderRunRequest

logger = logging.getLogger(__name__)
TERMINAL = {"SUCCEEDED": "succeeded", "FAILED": "failed", "ABORTED": "cancelled", "TIMED-OUT": "failed"}


class ApifyProvider:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        timeout = httpx.Timeout(self.settings.social_inventory_http_timeout, connect=min(10, self.settings.social_inventory_http_timeout))
        self._client = client or httpx.AsyncClient(base_url=self.settings.apify_api_base_url.rstrip("/"), timeout=timeout, follow_redirects=False)
        self._owns_client = client is None

    @property
    def actor_ids(self) -> dict[str, str | None]:
        return {name: getattr(self.settings, f"apify_{name}_actor_id") for name in BUILDERS}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider="apify", enabled=bool(self.settings.apify_api_token), platforms={key: bool(value) for key, value in self.actor_ids.items()}, reason=None if self.settings.apify_api_token else "APIFY_API_TOKEN is not configured")

    def _headers(self, request_id: str | None = None) -> dict[str, str]:
        if not self.settings.apify_api_token:
            raise SocialInventoryError("SOCIAL_PROVIDER_AUTH_FAILED", "Apify is not configured.", status_code=503)
        headers = {"Authorization": f"Bearer {self.settings.apify_api_token}", "Accept": "application/json"}
        if request_id:
            headers["X-Apify-Request-Id"] = request_id
        return headers

    async def _request(self, method: str, path: str, *, request_id: str | None = None, **kwargs) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.settings.social_inventory_max_retries + 1):
            response: httpx.Response | None = None
            try:
                response = await self._client.request(method, path, headers=self._headers(request_id), **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last = exc
                retry = True
            else:
                if response.status_code < 400:
                    return response
                retry = response.status_code == 429 or response.status_code >= 500
                if not retry:
                    if response.status_code in (401, 403):
                        raise SocialInventoryError("SOCIAL_PROVIDER_AUTH_FAILED", "Apify rejected the configured credentials.", status_code=502)
                    raise SocialInventoryError("SOCIAL_PROVIDER_FAILED", f"Apify rejected the request ({response.status_code}).", status_code=502)
                last = SocialInventoryError("SOCIAL_PROVIDER_RATE_LIMITED" if response.status_code == 429 else "SOCIAL_PROVIDER_FAILED", "The provider is temporarily unavailable.", retryable=True, status_code=503)
            if not retry or attempt >= self.settings.social_inventory_max_retries:
                break
            retry_after = float(response.headers.get("Retry-After", 0)) if response is not None else 0
            await asyncio.sleep(max(retry_after, min(2 ** attempt, 8)))
        if isinstance(last, SocialInventoryError):
            raise last
        raise SocialInventoryError("SOCIAL_PROVIDER_TIMEOUT", "The provider request timed out.", retryable=True, status_code=504) from last

    async def start_run(self, request: StartProviderRunRequest) -> ProviderRun:
        actor_id = self.actor_ids.get(request.platform)
        if not actor_id:
            raise SocialInventoryError("SOCIAL_PLATFORM_NOT_CONFIGURED", f"No Apify actor is configured for {request.platform}.", status_code=422)
        payload = BUILDERS[request.platform].build(request)
        response = await self._request("POST", f"/actors/{actor_id}/runs", request_id=request.request_id, json=payload)
        data = response.json().get("data", {})
        return ProviderRun(id=str(data["id"]), status="starting", dataset_id=data.get("defaultDatasetId"), metadata={"actor_id": actor_id})

    async def get_run(self, provider_run_id: str) -> ProviderRun:
        response = await self._request("GET", f"/actor-runs/{provider_run_id}")
        data = response.json().get("data", {})
        raw_status = str(data.get("status", "RUNNING")).upper()
        status = TERMINAL.get(raw_status, "running")
        return ProviderRun(id=provider_run_id, status=status, dataset_id=data.get("defaultDatasetId"), metadata={"raw_status": raw_status}, error_message=data.get("statusMessage"))

    async def get_items(self, provider_run_id: str, *, offset: int = 0, limit: int = 100) -> ProviderItemsPage:
        run = await self.get_run(provider_run_id)
        if not run.dataset_id:
            return ProviderItemsPage(items=[], offset=offset, limit=limit, has_more=False)
        response = await self._request("GET", f"/datasets/{run.dataset_id}/items", params={"offset": offset, "limit": limit, "clean": "true", "format": "json"})
        items: list[dict[str, Any]] = response.json()
        total = int(response.headers.get("X-Apify-Pagination-Total", offset + len(items)))
        return ProviderItemsPage(items=items, offset=offset, limit=limit, has_more=offset + len(items) < total)
