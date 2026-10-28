# Social Media Inventory

## Architecture

The React route `/social-inventory` only calls the local FastAPI API. Provider credentials never reach the browser. FastAPI creates an owner-scoped source and a durable row in `social_inventory_runs`; the standalone worker leases the row, starts or polls Apify, imports dataset pages, normalizes them, and commits every page. Expired leases are recoverable after a restart.

The current desktop application has no login system and identifies its single trusted local operator as `local-operator` through the replaceable `current_owner` dependency. Every source, run, item query, detail lookup, and export is scoped through that dependency.

## Database migration

Run `python -m alembic upgrade head`. Revision `0013_social_inventory` creates sources, durable runs, normalized items, metric snapshots, and comments. A second inventory uses external ID, then canonical URL, then stable content hash to update existing content. Changed metrics create a snapshot while `first_observed_at` is retained.

## Environment

Copy `.env.example` to `.env` and configure `APIFY_API_TOKEN` plus only the Actor IDs you use. Actor IDs are intentionally not embedded in Python. Supported keys are `APIFY_INSTAGRAM_ACTOR_ID`, `APIFY_TIKTOK_ACTOR_ID`, `APIFY_FACEBOOK_ACTOR_ID`, `APIFY_YOUTUBE_ACTOR_ID`, `APIFY_X_ACTOR_ID`, and `APIFY_LINKEDIN_ACTOR_ID`. Each platform owns an input builder in `providers/actor_inputs.py`; when changing an Actor, compare its current input schema and update only that builder.

`SOCIAL_INVENTORY_MAX_ITEMS`, comment limits, HTTP timeout, page size, and retry count enforce backend limits. The token is sent in the Authorization header, never a query string. Do not put credentials in frontend environment variables.

## Local operation

Start FastAPI with the existing command (`python -m backend.main`). In another activated environment run:

```powershell
python -m backend.social_inventory.worker
```

Use `--once` for one recoverable state-machine step. Start React from `frontend` with `npm run dev`. The worker must remain separate from the web process; it uses bounded polling backoff and database leases rather than FastAPI `BackgroundTasks`.

## Tests

```powershell
python -m pytest tests/test_social_inventory.py
python -m pytest
cd frontend
npm run test
npm run build
npm run test:e2e
```

Provider tests use `httpx.MockTransport`; they do not call Apify. The Playwright scenario mocks the FastAPI boundary and therefore needs neither paid Apify nor real Chrome login state. An optional live smoke test requires `RUN_LIVE_APIFY_TESTS=1`, `APIFY_LIVE_TEST_URL`, the token, and the matching Actor ID; it uses a dedicated public account with no more than three items and never runs in normal CI.

## Jev Social

Jev is disabled by default. Set `JEV_SOCIAL_ENABLED=true` and `JEV_SOCIAL_COMMAND` to a locally installed, verified read-only runner command. The adapter uses `asyncio.create_subprocess_exec` without a shell and only supplies fixed research arguments. It does not post, like, follow, message, bypass login gates, or claim partial/login-gated results as success. If the executable is absent, the UI explains the local requirement and Apify continues normally.

## Security and limitations

Only allowlisted HTTPS social hosts are accepted. Embedded credentials, IP literals, private/non-public DNS destinations, nonstandard ports, and cross-platform redirects are rejected. The feature collects public data only and does not bypass private accounts, CAPTCHAs, or provider terms. Raw provider rows are stored after recursively redacting tokens, authorization values, cookies, sessions, proxy credentials, and passwords. CSV/XLSX values beginning with `=`, `+`, `-`, or `@` are prefixed to prevent formula injection.

Rate limits and available fields depend on the configured Actor. Missing metrics remain null. A provider failure after some pages produces `partial`, retains imported rows, and records sanitized warnings. For troubleshooting, inspect the run status/error in the UI, verify the relevant Actor ID and token, and run one worker step with `python -m backend.social_inventory.worker --once`.
