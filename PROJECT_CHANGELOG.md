# Project Changelog

## 2026-09-03 — Local AI Video Generation Engine 1.0.0

- Added an isolated `backend/generation/video_engine` extension without changing the existing contract-first Generation Engine, Lead Acquisition, Sales, MSC, Workbook, or desktop workspace implementations.
- Added durable character identity memory for references, structured identity/style profiles, recurring attributes, negative constraints, versions, and checksums.
- Added reusable fixed master-prompt recipes that expand a short idea into positive/negative prompts, camera, lighting, color, environment, realism, motion, output, identity-lock, and deterministic script sections.
- Added config-driven routing for Wan Video, Hunyuan Video, AnimateDiff, and Stable Video Diffusion rather than hardcoding a single model.
- Added ComfyUI API-format workflow loading and node injection, reference upload, prompt queue submission, queue/history progress tracking, cancellation, output discovery, and output retrieval.
- Added a bounded dedicated GPU worker queue with durable queued/running/completed/failed/cancelled job state and retry support; no hardware diagnostics were added.
- Added project-relative video job/batch persistence and versioned EMY assets containing video, prompt, script, identity checksum, request, model/workflow, ComfyUI prompt, output-node, file checksum, and save state metadata.
- Added batch content-calendar input for up to 120 items, retaining calendar IDs and publish times across script → prompt → job → asset flow.
- Added `/video-studio` character, configuration, job, batch, progress, asset, content, retry, cancel, and save APIs.
- Added the feature-discovered desktop AI Video Studio with character upload, recipes, idea and output controls, progress polling, preview, asset save, batch queue, and asset library views.
- Added dedicated GPU deployment documentation and externally configurable ComfyUI workflow templates. Installation-specific node packs, model weights, and exported API graphs remain deployment inputs.
- Verification: all 134 backend tests passed, all 6 frontend files / 13 tests passed, Python compilation and the production TypeScript/Vite build passed, and project dependencies are consistent; no live GPU render was attempted on the development device.

## 2026-08-26 — Lead Data Acquisition Engine 1.0.0 — AUDITED COMPLETE

- Resumed at the exact interruption point: the Lead implementation had been committed after a backend regression stopped at 120 passed / 1 stale operator-capability assertion, before live source and native desktop proof. Existing working components were retained.
- Verified Alembic revision `0010_lead_acquisition`, all eight Lead tables, module imports, main-router endpoints, project-venv dependencies, source/credential status, API-backed React behavior, and absence of an external workbook.
- Completed only missing safety behavior: explicit HTTP 429 evidence, `WAITING_RATE_LIMIT` run/job/source state, checkpoint-preserving operator resume, and a bounded OSM Overpass path while retaining reusable Geofabrik PBF support.
- Live Overture Cairo/pharmacy smoke completed: 915 rows scanned, 10 real records returned, 10 unique canonical leads saved, zero errors, release `2026-08-19.0`.
- Live OSM Cairo/pharmacy smoke completed through a bounded Overpass BBOX: 10 real records returned and 10 unique canonical leads saved, with zero errors. No full Egypt PBF or nationwide plan was run.
- API verification found 20 persisted canonical leads / 20 source records, server pagination and filters, source/dedupe/score/provenance detail, and 20-row CSV (7,302 bytes), XLSX (9,190 bytes), and Parquet (12,227 bytes) exports.
- No HTTP 429, quota, daily-limit, billing, or credits-exhausted evidence was found. Google Places and Foursquare credentials are not configured; their adapters are interface-only and disabled, and no paid API credit was used.
- The optional control workbook was not found. Validated YAML fallback counts are 78 distinct keywords, 37 segments, and 27 governorates; a bounded Overture/Cairo/pharmacies dry run planned one job. The native default nationwide/Tier-1 dry run planned 514 jobs without collecting.
- Native Tauri/WebView2 verification opened Data Acquisition, New Run, Sources, Dry Run, Runs/progress, Results, and a real lead detail/provenance drawer. The explicit Start controls were present; the nationwide Start action was not clicked.
- Tests: all 126 backend tests passed; five frontend files / 10 tests passed; the production frontend build passed; the native window compiled, launched, stayed responsive, and shut down cleanly.
- Project state now marks `lead_data_acquisition_engine` complete. Portable Production Runtime remains next and was not started.

## 2026-08-25 — Desktop UI / Operator Control Center 1.0.0 — COMPLETE

- Task ID: `prompt_8b_desktop_ui_resume`; resumed the existing Desktop UI and removed only its Windows native-toolchain blocker. Portable Production Runtime / Prompt 9 was not started.
- Windows prerequisites: removed the canceled, incomplete Visual Studio Build Tools 2026 instance and its C:-hosted package residue, then installed Visual Studio Build Tools 2022 17.14.39 to drive D: with the `Desktop development with C++` workload and recommended components. The completed instance is launchable and reports no reboot requirement.
- Toolchain: MSVC v143 14.44.35207 / compiler 19.44.35228, Windows SDK 10.0.26100.0 with `rc.exe`, and Visual Studio CMake 3.31.6-msvc6 are available through the discovered developer environment. Installer cache/shared/toolchain storage was directed to D:; the obsolete 2026 instance recovered about 2.35 GB on C: before the SDK installed its required system components.
- Rust: installed rustup 1.29.0, rustc 1.98.0, Cargo 1.98.0, and the active/default `stable-x86_64-pc-windows-msvc` toolchain under D:-backed user tool directories. Node 24.18.0, npm 11.16.0, and WebView2 151.0.4129.107 were verified.
- Native development verification: `tauri info` recognized WebView2, Build Tools 2022, Rust, Cargo, and the MSVC target; `tauri dev` compiled 370 Rust/Tauri units, opened the responsive `EMY Control Center` native window, loaded the real WebView2 UI, and remained connected to the project-venv FastAPI backend.
- Native smoke/E2E: directly inspected the running Tauri WebView and navigated Home, Products, Customers, Sales, Inventory, MSC, Generation, Conversations, Approvals, and Settings with no route error. Local test data verified Product, Customer, Sales Order, Inventory Movement, and MSC Batch list/detail views.
- Answer Bot native regression: first conversation selection did not crash; a held draft rendered `PENDING REVIEW`, approved to `APPROVED` while retaining an enabled Send action, and sent through the deterministic mock channel to `SENT`.
- Generation native regression: a local synthetic READY contract enabled and created a non-executing queued job without calling a paid provider; the same contract marked NOT_READY disabled the action and displayed the blocked state.
- Build: optimized `tauri build` passed and produced `frontend/src-tauri/target/release/emy-control-center.exe` (8.67 MB, SHA-256 `3BA90346CCF31F89ECA135330F1B47120B2047730BC31351086B6743EA9AF2A9`). Bundling remains disabled for this development phase; no installer, signing, updater, portable Python, or production runtime work was performed.
- Tests: frontend dependency audit found zero vulnerabilities; 4 Vitest files / 8 unit-component-integration tests passed; TypeScript/Vite production compilation passed; live loopback operator endpoints passed; Alembic reached `0009_answer_bot`; dependency and compile checks passed; all 113 backend tests passed.
- Problems fixed: Vite now ignores `src-tauri` in its frontend watcher so Windows does not raise `EBUSY` while Cargo links executables; the Answer Bot follow-up max-attempt regression now uses a deterministic future non-quiet timestamp instead of a same-day time that could precede the schedule after noon.
- Project state: `desktop_ui` is complete, `active_task` remains null, and the next task is `portable_production_runtime`.

## 2026-08-22 — Desktop UI / Operator Control Center 1.0.0 — BLOCKED

- Task ID: `prompt_8_desktop_ui`; built the React/TypeScript control surface in the existing empty `frontend/` directory without starting portable production packaging.
- Added a feature-discovered application shell, collapsible navigation, top command/search bar, connection state, notification center, command palette, route-level error handling, RTL/LTR, light/dark/system themes, keyboard focus, and responsive desktop layouts.
- Added API-backed Home, Content, Intelligence, Patterns/Recipes, Rules, Generation, Assets, Calendar, Products, Customers, Sales, Inventory, Suppliers/Purchases, MSC, Conversations, Customer Service, Approvals, Analytics, Audit, and Settings routes. Lead and Publishing capabilities are explicitly unavailable rather than faked.
- Added shared server-paginated tables, status badges, drawers, loading/empty/error states, metric cards, provider views, contract-gated generation, three-column conversation review, Tauri-safe file selection, and safe local UI preferences.
- Added a typed timeout/error/request-ID API client with TanStack Query caching and adaptive 15–30 second refresh intervals.
- Added thin read-only operator APIs and repository/service boundaries for capabilities, health, dashboard, notifications, global search, safe settings, and paginated operational workspaces; enabled only explicit local/Tauri development CORS origins.
- Added Tauri 2 Rust scaffolding with bundling disabled, a restrictive CSP, and only core/default plus open-dialog permissions. No shell/process, unrestricted filesystem, updater, packaging, or signing capability was added.
- Dependencies: React 19, React DOM, React Router, TanStack Query, Lucide React, Vite 8, TypeScript, Vitest, Testing Library, Tauri 2 API/CLI, and the Tauri dialog plugin; npm reported zero vulnerabilities during installation.
- Tests: 8 frontend unit/component/integration tests passed, TypeScript/Vite production compilation passed, live loopback Vite/backend/CORS/capability smoke passed, 2 operator API tests passed, and all 113 backend regression tests passed when test TEMP/TMP were redirected to drive D:.
- Problems fixed: guarded the conversation detail transition before its first selection and kept approved outbound drafts visible and enabled for explicit manual sending.
- Environment: installed Rust/Rustup/Cargo 1.98.0 and verified the Cargo manifest; WebView2 151 is available.
- Blocker: Tauri diagnostics report the required MSVC C++ Build Tools and Windows SDK are absent. The official Build Tools installer returned exit code 1602. A GNU fallback failed and its package cache filled drive C:, so native `tauri dev` could not be compiled or launched.
- Project task/state remain unchanged because Prompt 8 explicitly forbids claiming success when the native Desktop application does not run.
- Next task remains `desktop_ui`; `portable_production_runtime` was not started.

## 2026-08-22 — Answer Bot, Customer Service, and Auto-Send Engine 1.0.0

- Task ID: `prompt_7_answer_bot`; completed only the Answer Bot/Customer Service/Auto-Send phase and left Desktop UI and portable runtime untouched.
- Verified the Product/Sales 1.0.0 prerequisite first with its focused 10-test suite, database context APIs, and existing revision `0008_product_sales`.
- Added 27 normalized models for channel/contact identity, conversations/messages/attachments/delivery, state, intent/entities, response plans/decisions, handoffs/notes/edits, follow-ups/consent, CRM/telesales, quote/order drafts, knowledge/templates/summaries, events, and webhook idempotency.
- Added `BaseMessagingChannel`, explicit channel availability, HMAC webhook verification, and deterministic no-network mock and local website-chat adapters; live connectors remain not configured.
- Added exact contact/customer/lead linking without fuzzy identity merges or automatic Customer creation.
- Added configurable Arabic, Egyptian Arabic, English, and mixed-language intent classification, multi-intent order preservation, confidence, sentiment/urgency/complaint severity, and validated product/SKU, quantity, budget, location/governorate, payment-method, order, invoice, customer-code, date, and requested-action entities.
- Added targeted read-only Product/Sales context for approved customer pricing, inventory availability, exact owned order/delivery state, balance, and versioned approved knowledge.
- Added response planning, deterministic local generation, prompt compilation, factual/safety validation, provenance, stale-data gates, unsupported-claim blocking, medical escalation, and prompt-injection defense.
- Added conservative Level 2 auto-send, human approval/edit audit, outbound idempotency, bounded retries/backoff, delivery events, dead-letter handoff, and no live sends in tests.
- Added human queues and factual summaries, consent-aware follow-ups with opt-out/quiet-hours/attempt limits, reviewable CRM signals, structured telesales tasks, and factual quote/order drafts that never post Sales Orders.
- Added Answer Bot APIs, credential-free YAML configuration, error mapping, Alembic revision `0009_answer_bot`, architecture documentation, and `docs/ANSWER_BOT.md`.
- Security decisions: `LOCAL_ONLY` provider enforcement, allow-listed read tools, targeted context, user text treated as untrusted, no secrets in config/logs, payment screenshots treated as unverified evidence, and transactional Product/Sales writes forbidden.
- Problems found and fixed: multi-intent precedence was incorrectly score-first; Decimal CRM entities were not JSON-safe; Windows lacked IANA timezone data; a deprecated UTC call remained; mock ingress could accept a non-mock channel label; and attachment metadata lacked managed-path validation/persistence.
- Tests: 20 focused Answer Bot tests passed; compileall, pip dependency checks, Alembic current/check, and the complete 111-test regression passed.
- Known issues: real messaging connectors and live integration tests require future credentials/permissions; fixed-offset quiet-hours configuration is used until timezone data is explicitly bundled; the earlier master workbook and FFmpeg limitations remain.
- Next task: `desktop_ui`.

## 2026-08-22 — Product / Sales Operating Engine 1.0.0

- Task ID: `product_sales_engine`; completed Prompt 6 only and did not start the Answer Bot, desktop UI, publishing, lead acquisition, or creator collection.
- Verified the Generation Engine prerequisite first (`21 passed`) and preserved the existing API → Service → Repository → Database architecture.
- Added Alembic revision `0008_product_sales` with 39 normalized tables for Product Master/versioning/batches, PriceBooks, customers, suppliers, warehouses, Inventory Ledger/reservations/stocktakes, sales orders/invoices/payments/collections, purchasing/AP, returns/distribution, daily close, MSC intake/staging, Accounting Bridge, approvals, business events, and audit.
- Added stable internal UIDs and unique business keys for SKU, customer, supplier, warehouse, order, invoice, payment, receipt, MSC, journal, event, and audit records.
- Implemented ProductService, PricingService, CustomerService, SupplierService, WarehouseService, InventoryService, SalesOrderService, InvoiceService, ReturnService, PaymentService, ReceivablesService, CollectionService, PurchaseService, SupplierPayablesService, DistributionService, DailyCloseService, MSCIntakeService, SalesSheetImportService, ProductSalesContextService, AccountingBridgeService, SalesReportingService, and SalesAuditService.
- Enforced approved/effective pricing, MOQ tiers, active customer/product checks, price-override approval, credit hold/limit, negative-stock blocking, invoice arithmetic, payment allocation limits, supplier receipt validation, daily-close exceptions, approved staging, and balanced journals.
- Kept current stock, customer AR, and supplier AP ledger-derived; no mutable stock/balance field or direct AI posting path was introduced.
- Added idempotency constraints and atomic transaction paths for orders, invoices, movements, payments, receipts, MSC batches/posting, journals, and event outbox records.
- Added MSC SHA-256 file hashing, generated project-relative filenames, MIME/extension/size/path checks, explicit sequence/page metadata, deterministic mock extractor, raw/evidence staging, confidence/identity/arithmetic validation, human approval, duplicate detection, and post-once behavior.
- Added CSV/XLSX Sales Sheet dry-run preview; found no existing workbook, so documented normalized future mappings in `docs/SALES_WORKBOOK_MAPPING.md` rather than inventing sheet mappings.
- Added read-only creative sales context with approved price/null behavior, stock availability, 7/30/90-day velocity, mover/priority signals, approved product facts, campaign eligibility, and reorder suggestions that never create purchase orders.
- Added delivery cost/charge separation, territory/sales representative architecture, Customer/Product/Supplier 360 services, operational reporting, daily-close reopen audit, and Trial Balance reporting.
- Added spreadsheet formula-injection hardening and retained data-plane separation: creators never enter sales tables and leads are only optional provenance on a separately identified customer.
- Added `docs/PRODUCT_SALES_ENGINE.md`, updated architecture/project memory, and added Product/Sales, MSC, inventory, accounting, migration, API, Decimal, path, security, idempotency, and atomic-posting tests.
- Problems found/fixed: normalized SQLite timezone-aware comparisons, updated migration regression expectations for the new schema, preflighted stock before financial posting, preserved order totals when invoicing reserved orders, moved supplier balance SQL behind the repository boundary, and extended fixture cleanup in foreign-key-safe order.
- Verification: Product/Sales `10 passed`; Generation `21 passed`; Rules `8 passed`; Pattern/Recipe `4 passed`; complete regression `91 passed`; `pip check` clean; `alembic check` reports no schema drift; migration upgrade/downgrade passes; absolute-path scan clean; no global pip use or live AI dependency.
- Known issues: no real sales workbook is present; live MSC extraction remains explicitly disabled; no full accounting/tax compliance claim is made; PostgreSQL scaling and external providers remain future configuration choices.
- Next task: `answer_bot`.

## 2026-08-19 - Multimodal Generation Engine 1.0.0

- Task ID: `generation_engine`; completed only after re-verifying the Pattern/Recipe and Rules Engine prerequisites.
- Models/Tables: added provider/model profiles, generation jobs/attempts/events, prompt packages/versions, generated assets/versions/references, QA runs/results, cost records, continuity states, storyboards/shots, and provenance records.
- Services: added the Generation Orchestrator, capability registry and selector, prompt compiler, safe asset storage/versioning, modality pipelines, retry/fallback, local queue, QA, character/temporal consistency, provenance, and cost tracking boundaries.
- Providers: added typed partial-capability provider and prompt-adapter contracts, health caching, normalized results, and deterministic local/remote mock providers; no paid or production provider call is enabled.
- Migrations: added and applied `0007_generation_engine`; Alembic reports head and no metadata drift.
- Tests: added contract, prompt, model/provider, modality, storyboard/continuity, storage/versioning/provenance, QA/human-review, accessibility, retry/max-retry/fallback/cache/cancellation, API, and security coverage. The final full regression passed 81 tests; compileall and dependency checks passed.
- Important decisions: Generation Contracts are mandatory and immutable; model selection is capability-based and local-first; provider details stop at adapters; outputs use project-relative content-addressed storage; video is shot-based; final approval is QA-gated; defaults are no-network mocks; live tests remain opt-in.
- Problems found: inline terminal state was not visible to the cache query because project sessions disable autoflush; Pydantic warned about the public `copy` field name; FFmpeg is absent.
- Problems fixed: explicitly flushed before idempotency lookup, retained the JSON `copy` contract through a safe alias, and used a manifest-only assembly boundary with no subprocess or shell execution. Security tests cover traversal, malicious filenames, unsupported MIME/extension pairs, shell-injection data, and secret redaction.
- Known issues: `MASTER_CONTROL_FILE_NOT_FOUND` remains because no canonical workbook is present; `FFMPEG_NOT_FOUND` limits final assembly to a safe manifest; real generation providers/models are intentionally not configured.
- Next task: `product_sales_engine`. Product/Sales work was not started.

## 2026-08-19 — Global Rules Engine 1.0.0

- Completed `Build Rules Engine` after verifying the Pattern/Recipe implementation and tests; Generation Engine work was not started.
- Added canonical versioned Rule/Rule Set models, effective dating, scopes, controlled actions, hard/soft behavior, configurable priority tiers, safe nested conditions, three-valued missing semantics, confidence/evidence gates, dependency ordering/cycle detection, and deterministic conflict resolution.
- Added Master Control preview/import/classification/compilation with file hashes, idempotency, change-created draft versions, undefined/integration-only exclusion, and `MASTER_CONTROL_FILE_NOT_FOUND` handling because no workbook is present.
- Added Recipe validation, non-mutating normalization, readiness decisions, immutable versioned Generation Contracts, scoped expiring overrides, non-overridable rules, human reviews, evaluation/result records, explanations, and high-impact audit events.
- Added Alembic revision `0006_rules_engine`, Rules/Rule Set/evaluation/explanation/import/override/review/Generation Contract APIs, `configs/rules.yaml`, and `docs/RULES_ENGINE.md`.
- Added synthetic unit, integration, API, security, versioning, conflict, dependency, import, and contract tests. Passed Rules (8), Pattern/Recipe (4), smoke (9), and full regression (60) tests, plus compileall, migration upgrade/downgrade, Alembic metadata check, and dependency health.
- Known issue: the canonical EMY Creative Generation Master OS workbook is not present; no runtime rules were invented from missing source material. Next task: `generation_engine`.

## 2026-08-17 — Pattern Mining, Content DNA, and Recipe Engine

- Read the project memory and architecture in the required order and extended the existing Analyzer, repository, service, API, configuration, and Alembic boundaries without duplicating them.
- Added idempotent, immutable Content DNA mapping from the latest usable analysis run with functional-segment order, normalized timing, observed temporal features, modality sections, confidence, evidence, and analyzer/taxonomy/engine provenance.
- Added availability-aware performance snapshots with raw and normalized values, sources, collection times, elapsed minutes, and organic/paid/mixed/unknown classification; no unavailable metric is fabricated and raw views are not treated as creative quality.
- Added configurable comparable cohorts using available platform, content type, category, language, country, duration, traffic, creator-size, and publication-period dimensions.
- Added deterministic pattern mining for single features, combinations, functional sequences, timing, editing, CTA, and cross-modal signals with minimum support count/ratio enforcement.
- Added low-confidence handling, observed/correlated/experimental/inferred evidence types, structural-only patterns when metrics are absent, and association-only performance summaries when comparable metrics exist.
- Added config-driven operational pattern scoring for support, confidence, performance association, consistency, and recency, plus conservative stability states and traceable content/segment/shot/result evidence.
- Added explainable DNA comparison, nearest-neighbor lookup, and lightweight threshold-based clustering without a heavy ML dependency.
- Added Recipe plans for pattern, top-performer, and creator-style sources with overfitting guardrails, general-characteristic copyright safeguards, insufficient-data status, source content/pattern/creator provenance, and “why this recipe” evidence.
- Added immutable Recipe versions and experiment-ready variants that record their base version, changed variables, overrides, optional experiment ID, and control recipe.
- Added Alembic revision 0005_pattern_recipe_engine with Content DNA, performance, pattern, mining-run, evidence-link, Recipe, version, source-link, and variant tables.
- Added DNA, similarity, clustering, pattern mining/list/detail/top, recipe build/list/detail/evidence, version, and variant APIs.
- Added configs/pattern_mining.yaml and docs/PATTERN_RECIPE_ENGINE.md, and updated the architecture documentation.
- Added a 24-item fictional analyzed-content fixture and tests covering DNA mapping/versioning/idempotency, support rejection, low confidence, sequence/timing/cross-modal mining, missing/performance association behavior, explainability, similarity/clustering, Recipe provenance, insufficient data, immutable history, variants, APIs, and database migration relationships.
- Passed all 52 tests, compileall, Alembic metadata agreement, migration upgrade/downgrade, and dependency health checks.
- Confirmed project-controlled files contain no machine-specific absolute path, the environment scripts use the project interpreter, and the global Rules Engine was not started.

## 2026-08-16 — Bootstrap

- Confirmed Python 3.14.3 through the Windows py launcher.
- Confirmed global pip 25.3 was available for the initial environment check only.
- Confirmed Git 2.53.0.windows.1 was available.
- Created the project-local .venv virtual environment.
- Verified the virtual environment executables and confirmed sys.prefix differs from sys.base_prefix.
- Upgraded pip inside .venv from 25.3 to 26.2.1.
- Created the project foundation directories.
- Created the project memory, configuration template, dependency, ignore, and README files.
- Added a relative-path Windows bootstrap script.
- Initialized a Git repository without creating a commit.
- Restored the pre-existing empty root.txt after the final review found it missing; its original zero-byte content is unchanged.
- Executed scripts/bootstrap_windows.bat successfully.
- Verified the required directories and foundation files are present.
- Validated project_state.json with the project virtual environment.
- Confirmed project-controlled files contain no hardcoded absolute Windows paths.
- Confirmed project executable files contain no global pip commands.
- Confirmed .venv is ignored by Git and no commit was created.
- Corrected an exclusion typo in the first verification command and reran the complete verification successfully; no project file was affected by the false-positive scan.

## 2026-08-16 — Core Architecture

- Read the project memory files before making architecture changes.
- Installed FastAPI 0.141.1, Uvicorn 0.52.3, Pydantic 2.13.4, pydantic-settings 2.15.0, SQLAlchemy 2.0.52, PyYAML 6.0.3, HTTPX 0.28.1, and pytest 9.1.1 inside .venv only.
- Pinned the compatible direct dependencies in requirements.txt.
- Added validated central settings sourced from environment variables, .env, and configs/app.yaml.
- Added a central project-relative path manager for data, database, models, assets, rules, taxonomy, logs, and configs.
- Added central logging and project-specific exception types.
- Created the FastAPI application, API router, and GET /health endpoint.
- Established the API → Service → Repository → Database dependency direction.
- Added the SQLAlchemy engine, session lifecycle, declarative base, system_meta model, and metadata repository.
- Created and verified database/emy_private_ai_os.db and the system_meta table.
- Added abstract connector, media analyzer, and image/video/copy generator contracts without external integrations or AI models.
- Added a YAML/JSON rules loader skeleton for taxonomy, extraction, generation, and sales rule documents.
- Added queue-neutral Job and JobExecutor abstractions with a synchronous local executor; no Redis or Celery was added.
- Added scripts/start_backend.bat using only the project interpreter and relative paths.
- Added docs/ARCHITECTURE.md and updated the README.
- Added database runtime files to .gitignore.
- Added tests for config, paths, database connectivity, health API, interface imports, and local job states.
- Replaced the deprecated TestClient path seen during an ad hoc probe with HTTPX ASGITransport in the committed health test.
- Used an in-process Uvicorn lifecycle test after terminal policy rejected external process-termination commands; no unknown process was started or stopped.
- Confirmed pip reports no broken requirements.
- Passed all 8 tests.
- Started Uvicorn on 127.0.0.1, verified the live /health response, and shut it down cleanly.
- Confirmed no hardcoded absolute Windows paths, global pip commands, forbidden feature implementations, or remaining architecture issues.

## 2026-08-16 — Database and Creator Master

- Read the project memory and architecture documents before inspecting only the database, API, configuration, connector, and test files related to this stage.
- Installed Alembic 1.19.1, openpyxl 3.1.5, and python-multipart 0.0.32 inside .venv and pinned them in requirements.txt.
- Added Alembic configuration, a baseline 0001_core revision, and the 0002_creator_master revision.
- Replaced startup create_all behavior with versioned Alembic upgrades.
- Detected the legacy system_meta-only database, stamped it at 0001_core, and upgraded it safely to 0002_creator_master.
- Added creators, platform_accounts, creator_import_batches, creator_import_errors, and content_items tables with indexes, foreign keys, unique identity constraints, and enum checks.
- Added stable CR_NNNNNN creator UID generation independent of usernames and platform logins.
- Added the possible_duplicate flag and conservative deduplication that refuses ambiguous cross-creator merges.
- Added platform, username, handle, profile-URL, and platform-ID normalization without network requests.
- Added config-driven column mapping for flexible CSV/XLSX creator sheets.
- Added managed data/imports storage and enforced project-relative paths in import and content ORM values.
- Added CreatorRepository, PlatformAccountRepository, CreatorImportRepository, CreatorService, and CreatorImportService.
- Added local Creator CRUD, account, search, and multipart import endpoints.
- Added ConnectorRegistry so future connectors can be selected by platform_accounts.platform without changing Creator.
- Added the Content Master relationship skeleton without collecting content.
- Added idempotent, non-sensitive Creator A/B demo seed data with Instagram, TikTok, and YouTube accounts.
- Removed the temporary CSV probe file created during early importer verification.
- Fixed Alembic Enum CHECK representation after alembic check detected schema drift; the final check reports no upgrade operations.
- Corrected multiline verification command formatting and reran the affected database and seed relationship checks successfully.
- Confirmed pip reports no broken requirements.
- Passed all 25 tests covering creators, account uniqueness and relationships, CSV, XLSX, normalization, deduplication, search, invalid rows, migrations, content relationships, connector readiness, health, paths, and existing core behavior.
- Verified live loopback API responses for /health and /creators.
- Confirmed no absolute paths in project-controlled files or database path fields, no global pip commands, and no commit.

## 2026-08-16 — Platform Connectors and Universal Content Collector

- Read the project memory and architecture files before inspecting only connector, content, persistence, job, API, configuration, and test code related to this stage.
- Extended BaseConnector with platform-neutral pagination and canonical NormalizedContent output.
- Added a ConnectorRegistry with explicit configured, not_configured, permission_required, and unsupported states; no fake production connector or real platform call was added.
- Added separate credential-free YAML configuration for Instagram, TikTok, YouTube, Facebook, Telegram, X, and Website.
- Added cursor, page-token, offset, and next-URL pagination abstractions with repeated-state protection.
- Added the UniversalContentCollector for Creator ID, Platform Account ID, profile URL, and single-content URL flows.
- Added resumable account cursor state and incremental last-collected timestamps.
- Expanded content_items into the canonical Content Master and added platform-scoped ID, URL, and content-hash deduplication.
- Preserved redacted raw responses before normalization under project-relative data/raw storage.
- Added a separate, opt-in MediaDownloader boundary under project-relative data/media storage; no network downloader is configured by default.
- Added bounded retries, exponential backoff, server rate-limit delay support, request rate limiting, terminal permission/invalid-account handling, and secret-safe structured logging.
- Added durable collection_runs jobs with queued, running, completed, partial, failed, and retrying states plus counters, cursors, options, and sanitized errors.
- Added local collection endpoints for creator, account, URL, job listing/detail, and connector status.
- Added Alembic revision 0003_platform_collector and verified upgrade, downgrade, and metadata agreement.
- Added mock-only tests for registry status, account resolution, normalization, pagination/resume, incremental sync, deduplication, cross-platform isolation, raw redaction, optional media, retry, rate limits, invalid/permission failures, manual URL routing, jobs, API, and persistence.
- Confirmed no Content Analyzer or real platform access was started.

## 2026-08-16 — Universal Content Analysis Engine

- Read Prompt 4 and the project memory in the required order, then inspected only Collector, Content, database, rules, analyzer, API, and test files relevant to this stage.
- Preserved the existing BaseAnalyzer and RulesEngine contracts and built the new analysis layer above them without rebuilding Creator or Collector modules.
- Added ContentRouter support for video/reel/short/live, image, carousel, audio, post/article, and mixed text-bearing content.
- Added validated external extraction rules and taxonomy documents with applies-to modalities, level, source, method, engine, output type, allowed values, confidence threshold, evidence requirement, and review policy.
- Added taxonomy guards that reject sensitive psychological/protected-trait inference fields and collector-only performance metrics as analysis outputs.
- Added a replaceable AnalysisEngine provider interface and isolated metadata, video-structure, vision, audio, speech, OCR, copy, behavioral-signal, and SEO registry entries.
- Added an embedded observable-evidence provider for the local first version; missing observations return UNKNOWN and non-applicable rules return NOT_APPLICABLE.
- Added a TimelineProvider boundary and normalized scenes, functional segments, shots, visual events, audio events, transcript/OCR text events, timestamps, bounding boxes, and evidence relationships.
- Added confidence normalization with accepted, low-confidence, manual-review, and failed result states.
- Added Alembic revision 0004_content_analysis with analysis_runs, content_segments, content_shots, analysis_results, visual_events, audio_events, and text_events.
- Added persistent queued, preprocessing, analyzing, normalizing, completed, partial, and failed analysis job states.
- Added streaming media hashes and cache keys containing analyzer, rules, taxonomy, provider, mode, and rule-subset versions; force reanalysis remains available.
- Added POST /analysis/content/{content_id}, POST /analysis/batch, GET /analysis/jobs/{job_id}, and GET /analysis/content/{content_id}, accepting numeric IDs or stable content UIDs where applicable.
- Added small local fixtures and tests for every content route, segments/shots/events, rule filtering, normalized schemas, confidence/evidence, UNKNOWN and NOT_APPLICABLE, cache/versioning, provider failure isolation, batch jobs, API, and persistence.
- Passed all 48 tests and verified compileall, Alembic metadata agreement, migration upgrade/downgrade, and dependency health.
- Confirmed no Pattern/Recipe Engine, winner detection, generation, sales, publishing, frontend, or external AI provider was started.
