# EMY PRIVATE AI OS — Project Root

## Project Name

EMY_PRIVATE_AI_OS

## Main Goal

Build a local, private, and portable AI operating system for content collection, analysis, generation, sales workflows, customer-service assistance, persistence, and a desktop interface.

## Architecture Principle

Local-first, private-first, portable, modular, config-driven, and API-first.

## Current Stack

- Windows
- Python 3.14.3
- Project virtual environment in .venv
- pip 26.2.1
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

## Important Paths

- backend/ — core API backend and extension contracts
- frontend/ — future desktop UI
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

SQLite is at Alembic revision 0009_answer_bot. In addition to the complete Analysis → DNA → Pattern → Recipe → Rules → Generation Contract and Product/Sales flows, it persists 27 Answer Bot tables covering normalized conversations/messages, channel/contact identity, state and understanding, response decisions, human handoff, outbound delivery, follow-ups/consent, knowledge/versioning, CRM/telesales, sales drafts, summaries, events, and webhook idempotency.

## Current Version

0.1.0

## Last Completed Work

Implemented and verified Answer Bot 1.0.0: channel abstraction/registry, normalized messages and conversations, exact contact/customer/lead linking, multilingual multi-intent/entity analysis, read-only grounded Product/Sales and versioned Knowledge context, response planning/generation/validation, conservative auto-send, approval queue/retries/idempotency, delivery state, human handoff, consent-aware follow-ups, CRM/telesales signals, factual sales drafts, APIs, migration, documentation, and security/integration/regression tests.

## Current Blockers

No Answer Bot execution blocker. Live messaging connectors are intentionally not configured; only no-network mock and local website-chat adapters are registered. Follow-up quiet hours use a configured fixed UTC offset because Windows does not bundle IANA timezone data. No sales workbook is currently present, and the earlier `MASTER_CONTROL_FILE_NOT_FOUND` and `FFMPEG_NOT_FOUND` limitations remain unchanged. Real messaging, MSC, generation, or conversation providers require explicit future configuration, credentials, permissions, and dedicated live tests.

## Next Step

Build the Desktop UI next. Do not start it, publishing, live messaging integrations, or portable runtime implicitly from the completed Answer Bot task.

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
