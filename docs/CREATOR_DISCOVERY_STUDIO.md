# Creator Discovery Studio

## Purpose and boundaries

Creator Discovery is an additive EMY module for discovering public creator accounts, reviewing identity evidence, retaining platform-specific records, sampling permitted public content, and exporting unified creator profiles. It reuses the existing Creator Master, platform-account normalizer, Content Master, Content Analyzer, FastAPI/SQLAlchemy/SQLite stack, and desktop shell. It is deliberately separate from Lead Acquisition.

The module does not bypass logins or CAPTCHAs, access private profiles, evade anti-bot controls, or fabricate unavailable values. Connectors expose `CONFIGURED`, `API_REQUIRED`, `MANUAL_URL_REQUIRED`, `NOT_CONFIGURED`, `NOT_AVAILABLE`, or `API_ERROR` instead of pretending a source is available.

No reference XLSX file was present in the supplied attachment or repository when this module was built. The export therefore implements the exact sheet and column schema written in the task specification. No source workbook was modified.

## Input and platform selection

The New Discovery surface accepts one name, a multiline list, or a bounded `.csv`/`.xlsx` upload. CSV/XLSX readers recognize common name headings and deduplicate inputs while preserving order. XLSX imports prefer the `EGYPT_MASSIVE_DUMP` sheet when present and otherwise read the active sheet.

Each run can select any combination of YouTube, Facebook, Instagram, TikTok, Snapchat, LinkedIn, and X. Direct platform-profile URLs are also accepted. A URL's source platform is resolved first, even when it was not selected explicitly. When its public display name is available, that name becomes the query for other selected connectors. Those additional candidates still enter human review.

The default limit is 10,000 inputs per run, 100 jobs per inline checkpoint, and 10 content samples per account. The sample size is operator-configurable from 1 to 30.

## Connector contract and current capabilities

`PlatformDiscoveryConnector` exposes capability reporting, candidate discovery, and recent-content collection. Seven independent connector classes implement the contract.

| Platform | Name discovery | Direct URL | Content sampling | Current implementation |
| --- | --- | --- | --- | --- |
| YouTube | `CONFIGURED` with API key; otherwise `API_REQUIRED` | Supported | `CONFIGURED` with API key; otherwise `API_REQUIRED` | Official YouTube Data API v3 search, channel, uploads-playlist, playlist-item, and video-detail paths; conservative URL fallback |
| Facebook | `API_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |
| Instagram | `API_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |
| TikTok | `API_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |
| Snapchat | `MANUAL_URL_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |
| LinkedIn | `API_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |
| X | `API_REQUIRED` | Supported | `API_REQUIRED` | Adapter boundary plus direct operator-supplied URL |

Set `EMY_CREATOR_DISCOVERY_YOUTUBE_API_KEY` in a non-committed `.env` file to enable the official YouTube connector. Secrets are never stored in YAML or returned by the capability endpoint.

`allow_public_page_fetch` is `false` by default. If an operator explicitly enables it in `configs/creator_discovery.yaml`, URL-first connectors request `robots.txt`, identify themselves as `EMY-CreatorDiscovery/1.0`, and only read public title/Open Graph metadata when the declared policy permits the URL. They do not use authenticated cookies or evasion.

## Candidate matching and review

The deterministic matcher records weighted evidence for normalized name, username similarity, bio similarity, linked/public cross-platform URLs, website domain, content-topic overlap, explicitly public location, brand names, profile naming consistency, and direct operator-supplied URL. Configuration lives in `configs/creator_discovery.yaml`.

Confidence is a 0–100 evidence score mapped to `CONFIRMED`, `HIGH_CONFIDENCE`, `POSSIBLE`, `REVIEW_REQUIRED`, or `REJECTED`. A name alone cannot reach the high-confidence threshold. A direct URL confirms that the operator selected that account URL, but it does not authorize a silent cross-platform merge.

Every discovered candidate enters Review Matches. The operator can choose This Is The Account, Not This Account, Merge into a specified Creator UID, or Keep Separate. Exact platform URLs, platform IDs, and normalized account identities cannot be attached to two Creator Master records. Fuzzy name matches only mark possible duplicates.

## Unified and platform-specific data

The unified profile stores the requested workbook fields plus `creator_uid`, normalized name, X URL, numeric influence size, confidence/status values, provenance, and history. Separate account records retain username, URL, metrics, bio, verification, first/last seen times, source IDs, source type, confidence, metadata, and provenance. Confirmed identities for platforms supported by the existing core enum are also mirrored into the existing Platform Account layer.

The creator detail drawer shows Unified Profile, Platform Accounts, Content Samples, Analysis, Match Evidence, Provenance, and History. Niche, industry, main platform, content style, KPI impact, and start year can be manually corrected; corrections are recorded as provenance/history and preserved during later analysis.

## Content collection and analysis

Connectors return at most the configured recent public sample. The YouTube API connector reads the public uploads playlist and video statistics when a valid key is configured. Other connectors return no sample until an authorized integration is configured. Missing metrics remain null internally and render/export as `UNKNOWN` or `NOT_AVAILABLE`.

Samples are stored independently and mirrored into Content Master where the existing platform model supports that platform. EMY's Universal Content Analyzer is invoked in text-only mode where evidence exists. A provider-neutral `CreatorAnalysisProvider` boundary produces the unified summary; the default provider is a deterministic, local evidence-rules implementation identified by provider and model version.

Analysis derives only what its stored evidence supports:

- niche and normalized industry from the versioned taxonomy;
- main platform from public audience size, then public activity, with explicit confidence;
- influence size from the maximum collected numeric follower/subscriber count;
- content mechanisms, format, CTA, commercial, education/entertainment, and posting patterns from samples;
- KPI labels only when public sample/engagement thresholds are met;
- start year only from an official profile creation date or the oldest sampled content.

Presentation/editing attributes remain `UNKNOWN` without suitable evidence. Provider output is never the source of truth for identity.

## Runs, checkpoints, refresh, and scale

Runs and jobs persist status, counts, attempts, errors, per-platform status, platform index, and a resolved-name checkpoint. Statuses are `PENDING`, `RUNNING`, `PAUSED`, `COMPLETED`, `PARTIAL`, `FAILED`, and `CANCELLED`. Pause, resume, and retry-failed operate on remaining/failed jobs rather than restarting completed work.

Creator lists, runs, and review candidates use server pagination. Filtering is executed in the repository for platform, industry, niche, numeric influence range, minimum match confidence, analysis status, and start year. React requests at most 50 rows per page.

Refresh updates existing public accounts, retains previous provenance, optionally resamples/reanalyzes, and starts a bounded discovery run for requested platforms not yet attached. Any newly found identities return to the review queue rather than being silently merged.

## Database

Alembic revision `0011_creator_discovery` adds these tables to the existing application database:

- `creator_discovery_runs`
- `creator_discovery_jobs`
- `creator_candidates`
- `creator_profiles`
- `creator_discovery_accounts`
- `creator_content_samples`
- `creator_analysis`
- `creator_match_evidence`
- `creator_sources`
- `creator_industries`

Stable UIDs, foreign keys, uniqueness constraints, and indexes support identity safety, audit history, paging, and retry. No second database is created.

## API

The principal endpoints are:

```text
GET    /creator-discovery/connectors
GET    /creator-discovery/industries
POST   /creator-discovery/runs
POST   /creator-discovery/runs/import
GET    /creator-discovery/runs
GET    /creator-discovery/runs/{run_uid}
POST   /creator-discovery/runs/{run_uid}/pause
POST   /creator-discovery/runs/{run_uid}/resume
POST   /creator-discovery/runs/{run_uid}/retry
POST   /creator-discovery/runs/{run_uid}/cancel
GET    /creator-discovery/candidates
GET    /creator-discovery/candidates/{candidate_uid}
POST   /creator-discovery/candidates/{candidate_uid}/confirm
POST   /creator-discovery/candidates/{candidate_uid}/reject
GET    /creator-discovery/creators
GET    /creator-discovery/creators/{profile_uid}
PATCH  /creator-discovery/creators/{profile_uid}
POST   /creator-discovery/creators/{profile_uid}/refresh
POST   /creators/export
POST   /creator-discovery/export
```

Existing core `/creators` and `/creators/{id}` APIs remain unchanged.

## Export mapping

Standard CSV and XLSX exports contain exactly these columns in order:

```text
Name
Niche
Industry
Main_Platform
YouTube
Facebook
Instagram
TikTok
Snapchat
LinkedIn
Content_Mechanism_Style
Influence_Size
KPI_Impact
Start_Year
```

Standard XLSX contains exactly `EGYPT_MASSIVE_DUMP` and `INDUSTRY_SUMMARY`. The summary has `Industry` and `Count` for the exported creator set. X is added only when Extended Export is explicitly chosen. CSV uses UTF-8 with BOM and spreadsheet-formula hardening.

## Limitations

- The supplied attachment contained instructions but no XLSX workbook, so structural compatibility is verified against the written schema rather than a physical workbook.
- Only YouTube has an implemented official automated connector, and it requires an operator-provided API key for name search, metrics, and samples.
- Facebook, Instagram, TikTok, Snapchat, LinkedIn, and X need approved APIs/permissions before automatic name discovery or content sampling can be claimed live.
- Public-page metadata is conservative, disabled by default, and may return only an operator-supplied URL when robots policy or page metadata does not permit enumeration.
- Cross-platform identity remains review-driven. Sparse public evidence deliberately yields `UNKNOWN`, `NOT_AVAILABLE`, or `INSUFFICIENT_EVIDENCE`.

## Bounded live verification

On 2026-09-05, a single URL-first run used the public `https://www.youtube.com/@mkbhd` profile with YouTube, Instagram, and X selected. The opt-in robots-aware reader found one YouTube candidate and stored its public name/profile metadata; Instagram and X returned `API_REQUIRED`. Human confirmation created one unified Technology profile with one retained YouTube account, one evidence-only analysis record, and field provenance. No content sample, follower count, KPI claim, or start year was fabricated. Standard export produced one row, 14 columns, and exactly the `EGYPT_MASSIVE_DUMP` and `INDUSTRY_SUMMARY` sheets at `data/creator_discovery/exports/creator_discovery_smoke.xlsx`.
