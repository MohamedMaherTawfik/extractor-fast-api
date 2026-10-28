"""Opt-in paid Apify smoke test; skipped in normal CI."""

import asyncio
import os

import pytest

from backend.core.config import get_settings
from backend.social_inventory.providers.apify import ApifyProvider
from backend.social_inventory.schemas import StartProviderRunRequest
from backend.social_inventory.url_validation import validate_social_url


@pytest.mark.skipif(os.getenv("RUN_LIVE_APIFY_TESTS") != "1", reason="live Apify test is opt-in")
def test_live_apify_three_public_items_maximum():
    settings = get_settings()
    url = os.getenv("APIFY_LIVE_TEST_URL")
    if not settings.apify_api_token or not url:
        pytest.skip("APIFY_API_TOKEN and APIFY_LIVE_TEST_URL are required")
    canonical, platform = validate_social_url(url, resolve_dns=True)

    async def smoke():
        provider = ApifyProvider(settings)
        try:
            run = await provider.start_run(StartProviderRunRequest(platform=platform, source_url=canonical, max_items=3, include_comments=False, max_comments_per_post=0, request_id="live-smoke"))
            for _ in range(60):
                state = await provider.get_run(run.id)
                if state.status in {"succeeded", "failed", "cancelled"}: break
                await asyncio.sleep(2)
            assert state.status == "succeeded", f"Apify run {run.id} ended as {state.status}"
            page = await provider.get_items(run.id, limit=3)
            print({"run_id": run.id, "status": state.status, "items": len(page.items)})
            assert len(page.items) <= 3
        finally:
            await provider.close()
    asyncio.run(smoke())
