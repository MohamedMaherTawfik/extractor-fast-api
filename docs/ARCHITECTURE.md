# EMY Private AI OS Architecture

## Core Flow

~~~text
React operator control center (development surface)
    ↓
FastAPI
    ↓
Services
    ↓
Rules / Connectors / Analyzers / Generators
    ↓
Repositories
    ↓
SQLite / Files / Models
~~~

API handlers validate transport concerns and delegate orchestration to services. Services coordinate domain interfaces and repositories. Only repositories access the database. Desktop UI code uses the typed HTTP API and does not call connectors, generators, AI models, or persistence directly.

## Configuration and Paths

Settings are validated by Pydantic and loaded in this priority order:

1. Explicit initialization values
2. Environment variables
3. Local .env overrides
4. configs/app.yaml
5. Code defaults

All filesystem locations are produced by backend/core/paths.py from the discovered project root. Runtime modules do not contain machine-specific paths. The SQLite database is stored at database/emy_private_ai_os.db.

## Persistence

SQLAlchemy provides the ORM boundary over SQLite. Alembic owns all schema creation and upgrades; application startup runs migrations to the current revision and never calls create_all. The schema currently contains:

- system_meta for application and schema versions
- creators as the stable identity master
- platform_accounts as a many-to-one identity layer
- creator_import_batches and creator_import_errors for auditable imports
- content_items as the normalized Content Master with platform-scoped identity, metrics, raw references, hashes, and optional media references
- collection_runs as durable queued/running/completed/partial/failed/retrying job state
- analysis_runs for versioned content and batch analysis jobs and cache keys
- content_segments and content_shots for scene, functional-segment, and shot timelines
- visual_events, audio_events, and text_events for timestamped observable evidence
- analysis_results for rule-linked values, confidence, evidence, source, engine, and review state
- content_dna for immutable analysis-to-DNA mappings and version provenance
- performance_snapshots for raw/normalized, availability-aware time-series metrics
- pattern_mining_runs, patterns, pattern_features, and pattern_content_links for explainable cohort mining
- recipes, recipe_versions, recipe_pattern_links, recipe_content_sources, and recipe_variants for editable generation plans
- rules, immutable rule_versions, rule dependencies, versioned rule sets/members, and scoped overrides
- master-control import runs and versioned classified controls for authoring provenance
- rule evaluation runs/results, human-review requests, and high-impact audit records
- immutable generation contracts and generation_contract_versions
- product/customer/supplier/warehouse masters and effective-dated product/price versions
- immutable inventory movements and reservations rather than mutable stock fields
- sales orders/invoices, payment allocations, receivables/collections, purchasing/payables, returns, and delivery
- MSC hashed intake files and approval-gated invoice staging
- daily close, balanced accounting journals, approvals, business-event outbox, and sales audit ledger
- messaging contacts/accounts, conversations, normalized messages/attachments/delivery events, state, intent/entities, response plans, decisions, handoffs, notes, edits, and audit events
- follow-ups, purpose-specific consent, CRM signals, telesales tasks, quote/order drafts, versioned knowledge/templates/summaries, and webhook idempotency records
- lead source registry, durable acquisition runs/jobs/checkpoints, canonical leads, source records/provenance, dedupe events, control-workbook imports, and separate consent-bearing opt-in leads

Creator identity is never derived from a username, login, email address, or hashtag. A creator_uid remains stable while platform accounts can be added or changed.

## Creator Master Flow

~~~text
Creator API / Import API
    ↓
CreatorService / CreatorImportService
    ↓
CreatorRepository / PlatformAccountRepository / CreatorImportRepository
    ↓
SQLAlchemy
    ↓
SQLite
~~~

CSV and XLSX files are copied into managed data/imports storage. Only their project-relative paths are stored. Column aliases come from configs/app.yaml. Exact account identifiers can safely select an existing creator; uncertain name matches are not merged and instead set possible_duplicate.

## Extension Interfaces

- Connectors normalize platform-specific data behind BaseConnector.
- ConnectorRegistry selects a connector from platform_accounts.platform without coupling Creator to any platform SDK. Platforms without authorized access are explicitly marked not_configured, permission_required, or unsupported.
- UniversalContentCollector resolves a saved account, traverses available pages, normalizes records, deduplicates within the platform, preserves redacted raw responses, and persists content and job state.
- PaginationState supports cursor, page_token, offset, and next_url strategies. PlatformAccount stores resumable cursor and incremental timestamps.
- Raw metadata collection is separate from the opt-in MediaDownloader boundary; all stored paths are project-relative.
- UniversalContentAnalyzer routes canonical content across one or more modalities, selects externally defined extraction rules, coordinates replaceable providers, and persists structured evidence-bearing output.
- AnalysisEngineRegistry isolates metadata, video structure, vision, audio, speech, OCR, copy, behavioral-signal, and SEO providers. The local default consumes canonical metadata or supplied observable evidence and returns UNKNOWN rather than inventing missing values.
- AnalysisRuleCatalog validates extraction rules against the taxonomy, rejects prohibited sensitive-inference fields and collector-only performance metrics, and applies thresholds and evidence requirements without hardcoding analysis fields in the orchestrator.
- The Generation Orchestrator consumes only immutable READY Generation Contracts and coordinates provider-neutral prompts, capability-based model selection, versioned assets, QA, retry/fallback, and provenance.
- Generation providers expose replaceable local-model, external-API, and custom-model backends behind typed partial-capability interfaces; the configured defaults are deterministic no-network mocks.
- RulesEngine loads taxonomy, extraction, generation, and sales documents from YAML or JSON outside application code.
- JobExecutor separates job submission from execution. InlineJobExecutor is local and synchronous; a future queue adapter can implement the same boundary.
- ContentDNAService maps normalized analysis into a versioned cross-content representation without inventing missing measurements.
- PatternMiningService mines supported feature, sequence, timing, and cross-modal patterns inside comparable cohorts; PatternScoringService applies config-driven operational ranking.
- ContentSimilarityService provides deterministic DNA comparison and lightweight clustering.
- RecipeBuilderService and RecipeVersionService build provenance-rich plans, preserve history, and model experiment variants without generating media.
- RulesEngine composes effective versioned rules, safely evaluates structured conditions with three-valued logic, orders dependencies, resolves conflicts, and persists explainable decisions.
- RecipeRuleValidationService and GenerationContractService normalize copied Recipe plans and freeze readiness requirements without invoking a generator.
- BaseMessagingChannel and ChannelRegistry isolate normalized conversation processing from provider webhooks and outbound delivery; only no-network mock and local website-chat adapters are registered.
- AnswerBotEngine coordinates contact resolution, multilingual intent/entity analysis, allow-listed read-only Product/Sales context, response planning/generation/validation, conservative auto-send, human handoff, follow-up, consent, and reviewable CRM/sales drafts.
- ConversationModelProvider isolates local or future external language providers. The default deterministic provider is local, and LOCAL_ONLY mode prevents external selection.
- LeadSourceRegistry reports each source independently and selects streaming collectors. Overture and OSM/Geofabrik are implemented and enabled without credentials; Google Places, Foursquare, website enrichment, official registry, and licensed-directory adapters remain explicitly gated or disabled.
- LeadAcquisitionService plans tiled jobs, persists checkpoints and raw project-relative records, normalizes source payloads, performs deterministic multi-signal deduplication and scoring, and exposes server-paginated canonical results. HTTP 429 evidence is retained as `WAITING_RATE_LIMIT` without an automatic aggressive retry.

No real platform API implementation, scraper, paid lead-provider implementation, or live messaging connector is fabricated. No external or fine-tuned analysis, generation, or conversation model is configured: those implementations can replace provider interfaces later. Causal winner claims, publishing, and authentication remain unimplemented. The React operator surface and native Tauri shell are implemented and verified. The Answer Bot never mutates Product/Sales source records and stops order drafts at sales review.

## Desktop Operator Surface

~~~text
Tauri WebView / Vite development surface
    -> feature-discovered shell + route error boundaries
    -> typed API client + TanStack Query server cache
    -> thin OperatorService / OperatorRepository read models
    -> existing domain APIs, services, repositories, and SQLite
~~~

The operator surface never computes business facts. `GET /system/capabilities` gates navigation; Lead Acquisition is available while Publishing remains unavailable. Dashboard, search, notifications, health, safe settings, and server-paginated workspace endpoints expose real backend state without secrets. See `docs/DESKTOP_UI.md` for routes, security, RTL/LTR, and testing.

## Lead Acquisition Flow

~~~text
Source registry + workbook/YAML controls
    -> dry-run planner -> durable run and tiled jobs
    -> Overture or OSM/Geofabrik collector
    -> project-relative raw JSONL + checkpoint
    -> normalization -> deterministic dedupe -> deterministic score
    -> canonical lead + source provenance -> SQLite
    -> paginated API/export -> native Data Acquisition workspace
~~~

The optional command workbook can supply Lead Segments, Keyword Master, Egypt Coverage, Source Registry, Query Matrix, and Run Config. If absent, the validated YAML catalog remains the explicit source of truth. Full-Egypt execution is operator initiated; audits use bounded BBOX samples only. See `docs/LEAD_DATA_ACQUISITION_ENGINE.md`.

## Collection Flow

~~~text
Creator / Platform Account / Manual URL
    ↓
UniversalContentCollector + persistent CollectionRun
    ↓
Connector Registry → isolated BaseConnector implementation
    ↓
Pagination → raw redacted storage → canonical normalization
    ↓
Platform-scoped deduplication → ContentRepository → SQLite
    ↓
Optional MediaDownloader → project-relative data/media path
~~~

The current executor is synchronous and local, while the persisted job boundary and stateless connector contract allow a future remote worker to invoke the same service pipeline.

## Analysis Flow

~~~text
Content Item
    ↓
ContentRouter → one or more modalities
    ↓
AnalysisRuleCatalog → taxonomy-validated applicable rules
    ↓
TimelineProvider + isolated AnalysisEngine providers
    ↓
Confidence/Evidence Normalizer → UNKNOWN / NOT_APPLICABLE / accepted / review
    ↓
AnalysisRepository → runs, segments, shots, events, and results
~~~

Media hashing reads local files in configurable chunks. Cache keys include media hash, analyzer version, rules version, taxonomy version, engine versions, mode, and selected rules. Engine failures produce partial jobs while preserving successful results. No platform performance metric is treated as vision or language-model output.

## Pattern and Recipe Flow

~~~text
Analysis + Timeline + Evidence
    → Content DNA + normalized performance snapshots
    → comparable cohorts
    → supported explainable patterns + operational score
    → editable Recipe v1 → Recipe v2 / experiment variants
~~~

Patterns without metrics stay structural. Performance evidence is labeled as association rather than causation. See `docs/PATTERN_RECIPE_ENGINE.md` for types, thresholds, provenance, APIs, and examples.

## Rules and Decision Flow

~~~text
Master controls → preview/classification → Rule Compiler → versioned registry
    → effective scope + Rule Sets + Recipe/context
    → safe TRUE/FALSE/UNKNOWN evaluation
    → dependency/conflict resolution → auditable readiness decision
    → immutable Generation Contract
~~~

SQLite is the runtime source of truth; master spreadsheets are import contracts only. See `docs/RULES_ENGINE.md` for machine schemas, lifecycle, safety, overrides, and API details.

## Multimodal Generation Flow

~~~text
READY Generation Contract + references + output specification
    -> neutral versioned Prompt Package
    -> capability registry + local-first model selection
    -> provider adapter -> normalized result
    -> relative hashed asset + immutable Asset Version + provenance/cost
    -> technical/domain/accessibility/rights QA
    -> approval, human review, retry/fallback, or typed failure
~~~

Video generation is shot-based and persists continuity state. Copy, image, video, audio, captions, transcripts, and audio-description drafts share one orchestrator while retaining modality-specific pipelines and QA. The queue, provider, provenance-signing, and video-assembly boundaries are replaceable; current defaults are synchronous local mocks, deferred C2PA, and a safe manifest-only assembly plan. See `docs/GENERATION_ENGINE.md`.

## Future Shared Workflows

~~~text
Creator
    → Accounts
    → Content
    → Analysis
    → Patterns
    → Generation

Products
    → Pricing
    → Sales
    → Answer Bot
    → Orders
~~~

Both workflows will share the same configuration, path management, API, service, repository, job, and persistence core.

## Answer Bot Flow

~~~text
Channel adapter -> normalized Message -> Contact + Conversation
    -> Intent + Entities + ConversationState
    -> allow-listed Product/Sales + approved Knowledge context
    -> ResponsePlan -> local provider draft -> safety/fact validation
    -> bounded outbound queue OR HumanHandoff
    -> consent-aware FollowUp + reviewable CRM/telesales/sales drafts + audit
~~~

Facts are selected per intent and carry source/version provenance. Low-confidence, sensitive, disputed, ambiguous, stale, or unsupported requests cannot auto-send. See `docs/ANSWER_BOT.md`.

## Local Runtime

The portable Windows launcher uses the project interpreter directly and does not require virtual-environment activation. Host configuration is restricted to the local loopback interface for this stage.
