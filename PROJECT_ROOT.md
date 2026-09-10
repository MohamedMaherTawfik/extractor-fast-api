# EMY PRIVATE AI OS — Project Root

## Project Name

EMY_PRIVATE_AI_OS

## Main Goal

Build a local, private, and portable AI operating system for content collection, analysis, generation, sales workflows, customer-service assistance, persistence, and a desktop interface.

## Architecture Principle

Local-first, private-first, portable, modular, config-driven, and API-first.

## Current Stack

- Windows
- Python 3.14.6
- Project virtual environment in .venv
- pip 26.1.2
- Git 2.53.0.windows.1
- FastAPI 0.141.1
- Uvicorn 0.52.3
- Pydantic 2.13.4 with pydantic-settings 2.15.0
- SQLAlchemy 2.0.52
- SQLite
- Alembic 1.19.1
- openpyxl 3.1.5
- python-multipart 0.0.32
- YAML and .env configuration
- Node.js 24.18.0 and npm 11.16.0
- React 19, TypeScript 7, Vite 8, and Tauri 2
- Rust/Cargo 1.98.0 with the stable x86_64-pc-windows-msvc toolchain
- Visual Studio Build Tools 2022 with MSVC v143 and Windows SDK 10.0.26100.0
- Microsoft Edge WebView2 Runtime 151

## Current Modules

- Bootstrap foundation
- Central configuration and path manager
- FastAPI application and health endpoint
- SQLAlchemy session and SQLite database core
- system_meta ORM model and repository
- Health service following API → Service → Repository → Database
- Connector interface
- Analyzer interfaces
- Generator interfaces
- External rules loader skeleton
- Queue-neutral job abstraction with local inline execution
- Versioned database migrations
- Creator Master and platform-account identity layer
- Config-driven CSV/XLSX creator import with audit batches and row errors
- Account normalization and deduplication
- Creator search API
- Connector registry readiness
- Explicit connector availability and per-platform credential-free configs
- Universal Content Collector for creators, accounts, and manual URLs
- Cursor/page-token/offset/next-URL pagination and incremental sync state
- Canonical Content Master with platform-scoped deduplication
- Persistent collection jobs with retry, backoff, and rate limiting
- Redacted raw-response preservation and opt-in media download boundary
- Rules-driven Universal Content Analysis Engine
- Mixed-content routing for video, image, carousel, audio, and text
- Replaceable metadata, video-structure, vision, audio, speech, OCR, copy, behavior, and SEO providers
- Normalized analysis runs, segments, shots, visual/audio/text events, and evidence-bearing results
- Confidence thresholds, UNKNOWN/NOT_APPLICABLE handling, review flags, caching, and full version provenance
- Content and batch analysis API
- Versioned, idempotent Content DNA mapping across supported content types
- Availability-aware performance snapshots and normalized engagement rates
- Comparable-cohort pattern mining for features, combinations, sequences, timing, and cross-modal signals
- Config-driven support thresholds, confidence policies, scoring weights, and similarity weights
- Explainable pattern evidence with explicit observation/correlation/experiment/inference types
- Deterministic Content DNA comparison, nearest-neighbor similarity, and lightweight clustering
- Editable, reusable, version-preserving Recipe plans with provenance and experiment variants
- Pattern, DNA, similarity, clustering, and Recipe APIs
- Central, versioned, auditable Global Rules Engine with safe structured conditions and three-valued logic
- Rule scopes, effective dating, confidence/evidence gates, dependencies, priority and conflict resolution
- Versioned Rule Sets, controlled overrides, human-review requests, and high-impact audit records
- Master-control preview/import/classification/compiler boundary with idempotency and change detection
- Recipe validation/non-mutating normalization, generation readiness, and immutable versioned Generation Contracts
- Rules, Rule Set, evaluation/explanation, import, review, override, and Generation Contract APIs
- Contract-first multimodal Generation Orchestrator with preview, execution, retry, fallback, cancellation, cache, and event history
- Provider abstraction, normalized results, provider prompt adapters, persistent provider/model registry, and capability-based local-first selection
- Versioned provider-neutral Prompt Packages with character, brand, product, reference, constraint, accessibility, QA, and provenance sections
- Structured copy/script/storyboard pipelines, image generation/edit boundaries, shot-based video with continuity state, and audio/voice/SFX/accessibility pipelines
- Project-relative content-addressed generated-asset storage, immutable asset versions, checksums, provenance/C2PA boundary, cost records, and archival
- Technical, schema, character, product, brand, visual, copy, audio, accessibility, rights, provenance, and temporal-continuity QA with human-review integration
- Generation job/provider/model/asset/provenance APIs and deterministic no-network mock providers for default local verification
- Versioned Product Master with unique SKU business identity and effective-dated snapshots
- Approved effective-dated PriceBooks with retail/wholesale/segment and MOQ quantity tiers
- Customer Master with optional converted-lead provenance, credit controls, and ledger-derived receivables
- Supplier/Warehouse masters, purchase orders, goods receipts, supplier invoices, and ledger-derived payables
- Immutable Inventory Movement Ledger, reservations, transfers, stocktakes, batch/lot metadata, and negative-stock policy
- Approval-aware sales orders, immutable posted invoices, returns, delivery/distribution, territories, and sales representatives
- Payments with partial/multi-invoice allocations, customer statements, AR aging, and collections workflow
- Hash/sequence-aware MSC file intake, extractor boundary, raw staging, confidence/match validation, approval, and atomic idempotent posting
- Sales Sheet CSV/XLSX dry-run preview and documented workbook-to-domain mapping boundary
- Daily Close exceptions/reopen workflow, balanced Accounting Bridge journals, and Trial Balance reporting
- Read-only Product Sales Context with velocity, mover, priority, campaign eligibility, and non-posting reorder suggestions
- Transactional business-event outbox, sales approval requests, and append-only mutation audit ledger
- Omnichannel messaging adapter contract and explicit channel registry with deterministic mock/local website-chat implementations
- Normalized messaging contacts, conversations, messages, attachments, delivery events, conversation state, intent/entities, and response decisions
- Multilingual and multi-intent classification, validated exact business entities, and targeted read-only Product/Sales context
- Versioned approved Knowledge Base, response planning/generation/validation, provenance, and prompt-injection/medical safety gates
- Conservative Level 2 auto-send, approval-aware outbound queue, idempotency, bounded retry, delivery status, and dead-letter handoff
- Human handoff queues/summaries, agent edit audit, consent-aware follow-ups, opt-out/quiet-hours enforcement, and CRM signals
- Reviewable telesales tasks and factual quote/order drafts that never post Product/Sales transactions
- Native Windows Desktop UI / Operator Control Center with feature-discovered navigation, API-backed workspaces, Tauri security boundaries, RTL/LTR themes, generation gating, and conversation review/send workflows
- Lead Data Acquisition Engine with governed source registry, Overture and OSM/Geofabrik collectors, resumable durable runs, deterministic normalization/deduplication/scoring, provenance, server-paginated results, and CSV/XLSX/Parquet export
- Dedicated local AI Video Studio with character identity memory, reusable master-prompt recipes, config-routed Wan/Hunyuan/AnimateDiff/SVD ComfyUI workflows, durable GPU queue progress, versioned assets, and content-calendar batching
- Multi-Platform Creator Discovery Studio with seven capability-reporting adapters, URL/name/CSV/XLSX input, deterministic evidence matching, human identity review, unified profiles, content-analysis integration, checkpointed runs, provenance, server pagination, refresh, and exact-schema CSV/XLSX export

## Important Paths

- backend/ — core API backend and extension contracts
- frontend/ — React/Vite frontend and Tauri 2 native desktop shell
- database/ — local SQLite database assets
- database/migrations/ — versioned Alembic schema
- configs/ — configuration files
- rules/ — business and generation rules
- taxonomy/ — taxonomy definitions
- models/ — local model metadata and related assets
- assets/ — project assets
- data/ — local project data, managed imports, redacted raw responses, and opt-in media
- logs/ — local runtime logs
- scripts/ — maintenance and bootstrap scripts
- tests/ — automated tests
- docs/ — project documentation

## Database Status

SQLite is at Alembic revision `0011_creator_discovery`. Creator Discovery adds durable runs/jobs, candidates, unified profiles, platform accounts, content samples, analyses, match evidence, field provenance, and an extensible industry taxonomy to the existing application database.

## Current Version

0.1.0

## Last Completed Work

Implemented Creator Discovery Studio 1.0.0 as an isolated extension. It adds seven explicit platform adapter boundaries, official YouTube Data API support, URL/name/file input, deterministic match evidence and review, unified and platform-specific records, evidence-only analysis, run checkpoints, refresh, a dedicated desktop workspace, and exact written-schema exports. Automated platform coverage remains partial until approved APIs are configured.

## Current Blockers

No Creator Discovery module or Desktop UI execution blocker. The referenced Creator Discovery XLSX was not included, so export compatibility is verified against the exact written sheet/column schema. YouTube API support has no configured key; the other six platforms require approved API integrations for automatic discovery/sampling. The optional Lead control workbook is also absent, and existing lead-source, messaging, timezone, master-control workbook, GPU-workflow, and FFmpeg limitations remain unchanged.

## Next Step

Configure only the approved creator-platform APIs needed for broader live discovery, then build the Portable Production Runtime. Do not start a mass creator crawl, full-Egypt lead run, installer engineering, signing, publishing, or paid provider integrations implicitly.

## Non-negotiable Rules

- Local-first
- Private-first
- Portable architecture
- No absolute paths
- No hardcoded credentials
- Config-driven
- Modular architecture
- API-first backend
- Do not duplicate existing modules
- Inspect existing files before changing them
- Never install packages globally
- Always use project virtual environment
