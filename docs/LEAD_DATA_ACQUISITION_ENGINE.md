# Lead Data Acquisition Engine 1.0.0

## Scope and safety boundary

The Lead Data Acquisition Engine discovers public Egypt business POIs, keeps source provenance, and produces a separate canonical business-lead domain. It does not create customers, post sales transactions, infer consent, or place collected POIs in `opt_in_leads`. A full-Egypt run is never automatic.

The runtime flow is:

~~~text
workbook or YAML controls -> dry-run plan -> durable jobs
  -> source collector -> project-relative raw JSONL + checkpoint
  -> normalizer -> deterministic dedupe -> deterministic scoring
  -> canonical Lead + SourceRecord + DedupeEvent
  -> paginated API/export -> native desktop workspace
~~~

## Sources

| Source | Implementation | Default state | Credentials | Audit proof |
| --- | --- | --- | --- | --- |
| Overture Maps Places | Official Python client, release discovery, BBOX streaming | Enabled / ready | None | Live Cairo BBOX completed |
| OSM / Geofabrik | Reusable Egypt PBF streaming plus bounded Overpass BBOX mode | Enabled / ready | None | Live bounded Overpass query completed |
| Foursquare Places | Config-gated interface only | Disabled | Required, not configured | No paid request made |
| Google Places | Config-gated interface only | Disabled | Required, not configured | No paid request made |
| Website enrichment | Config-gated interface only | Disabled | None | Not live |
| Official registry | Config-gated interface only | Disabled | Endpoint/permission required | Not live |
| Licensed directory | Registry declaration only | Disabled | Permission/license required | Not live |

Each source has an independent persisted status, last run, last success, terms state, storage policy, and rate-limit policy. One unavailable source does not make the engine unavailable.

HTTP 429 responses preserve the source, status code, provider message, `Retry-After`, and provider reset header when supplied. Missing reset information is recorded as `RESET_TIME_UNKNOWN`. The job and run enter `WAITING_RATE_LIMIT`; an operator can resume from the saved checkpoint after the provider permits it. There is no aggressive automatic retry loop.

## Controls and workbook

The optional workbook location is `data/imports/lead_control/EMY_Egypt_Lead_Acquisition_OS_v*.xlsx`. The importer validates these sheets: `Lead Segments`, `Keyword Master`, `Egypt Coverage`, `Source Registry`, `Query Matrix`, and `Run Config`. Imports are copied to managed project-relative storage and recorded with a SHA-256 hash and sheet counts.

No workbook was present during the 2026-08-26 audit. The validated `configs/lead_acquisition.yaml` fallback supplied 78 distinct keywords, 37 segments, and all 27 governorates. A bounded Overture/Cairo/pharmacies dry run planned one job. The desktop default nationwide Tier-1 dry run planned 514 jobs and performed no collection.

## Persistence and result behavior

Alembic revision `0010_lead_acquisition` owns eight tables: `lead_sources`, `lead_runs`, `lead_jobs`, `leads`, `lead_source_records`, `lead_dedupe_events`, `lead_control_imports`, and `opt_in_leads`.

Jobs persist raw position checkpoints, counters, status, source/geography/category, attempts, errors, and project-relative raw paths. Pause, resume, cancel, retry-failed, and rate-limit resume operate on those durable records.

Canonical matching considers exact source identity, normalized phone, normalized domain, normalized name/address, proximity, and cross-source evidence. Distinct branches remain distinct even when a chain phone matches. Every accepted or merged record retains source/version/run/tile/keyword provenance.

Fit class is computed by versioned deterministic weights for category fit, commercial scale, professional consumption, resale potential, contactability, freshness, geography, and verification. Thresholds are `A+ >= 85`, `A >= 70`, `B >= 50`, and `C >= 0`; AI does not assign the class.

## API and desktop

The main FastAPI router exposes:

- `GET /lead-sources` and `GET /lead-control`;
- `POST /lead-control/workbook/import`;
- `POST /lead-runs`, `GET /lead-runs`, and `GET /lead-runs/{run_uid}`;
- `POST /lead-runs/{run_uid}/pause|resume|cancel|retry`;
- `GET /leads`, `GET /leads/{lead_uid}`, and `GET /lead-stats`;
- `POST /leads/export` for CSV, XLSX, or Parquet.

Result queries enforce server-side offset/limit pagination with a maximum page size of 500 and support class, governorate, category, source, verification, and text filters. React never loads every lead to implement filtering.

The native Data Acquisition route includes Overview, New Run, Runs, and Results. It exposes source readiness, workbook counts/warnings, dry-run planning, explicit start, durable progress and controls, server-side result filters, export, and canonical/source/dedupe/score/provenance detail. The prominent full-Egypt action still requires an explicit operator click.

## 2026-08-26 bounded live audit

- Overture: Cairo pharmacy BBOX, 915 source rows scanned, 10 matched, 10 unique leads saved, release `2026-08-19.0`.
- OSM: Cairo pharmacy BBOX through the bounded Overpass mode, 10 matched, 10 unique leads saved.
- Persisted/API/native result: 20 canonical leads and 20 source records, all with real coordinates and source provenance; Overture samples also contained public phone, website, and address fields.
- Export: CSV 20 rows / 7,302 bytes, XLSX 20 rows / 9,190 bytes, and Parquet 20 rows / 12,227 bytes.
- Rate/quota evidence: none. No HTTP 429, quota, billing, or daily-limit response occurred, and no paid provider request was made.
- Verification: 126 backend tests passed; five frontend test files with 10 tests passed; the production frontend build passed; the responsive native Tauri/WebView2 route passed its live smoke.

The audit did not run the full-Egypt plan and did not start Portable Production Runtime work.
