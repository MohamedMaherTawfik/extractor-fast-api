# Multimodal Generation Engine

## Scope and safety boundary

The Generation Engine turns an immutable, `READY` Generation Contract into versioned copy, script, storyboard, image, video, audio, or accessibility assets. It does not make sales decisions, publish content, implement an answer bot, or provide a UI.

The default configuration is local-first and registers deterministic mock providers only. Automated tests never call a network service or a paid model. Production providers must be added behind the provider interface and explicitly configured; credentials do not belong in the model registry, database, prompt packages, logs, or repository.

## Execution flow

```text
READY Generation Contract (exact version)
    -> provider-neutral Prompt Package + stable hash
    -> required capability calculation
    -> Model Registry selection (local-first by policy)
    -> queued Generation Job
    -> provider adapter + normalized provider result
    -> safe relative asset storage + immutable asset version
    -> provenance + cost records
    -> category QA gates
    -> approved completion, human review, retry/fallback, or failure
```

`POST /generation/preview` performs contract validation, compilation, capability selection, and estimation without calling a provider or creating an asset. Normal creation is idempotent for the same contract version, prompt, primary model, seed, references, and output specification. `fresh_variation=true` bypasses that cache while preserving the changed-variable declaration.

## Contract and prompt boundary

Every request supplies a Generation Contract identifier and version. The orchestrator rejects missing versions, non-current versions, mutable/non-ready contracts, and references that are not both approved and rights-cleared.

`PromptCompiler` creates a structured, provider-neutral package containing:

- objective, modality, content type, and platform;
- versioned character, brand, and product context;
- scene, visual, camera, lighting, performance, copy, and audio plans;
- positive, negative, and forbidden-change constraints;
- reference roles and per-reference priority controls;
- output, accessibility, QA, evidence, and provenance requirements;
- ordered sections with source, hardness, and priority.

Explicit hard constraints are applied to a copied recipe; the stored Generation Contract is never mutated. Conflicting positive and negative instructions fail before provider execution. Every persisted prompt version has a deterministic hash and a recorded change reason.

## Provider and model architecture

`BaseGenerationProvider` exposes typed partial capabilities for text, image generation/editing, video, and audio, plus asynchronous submit/status/fetch/cancel hooks. Unsupported operations fail with a typed capability error. `ProviderPromptAdapter` is the only layer that translates the neutral prompt contract into provider-shaped input. Provider responses are normalized into media assets, structured text outputs, metadata, timing, cost, warnings, errors, and an optional redacted raw-response reference.

`ModelCapabilityRegistry` persists provider/model profiles from `configs/generation.yaml`. Selection is capability-based, not model-name-based. It considers modality, structured output, seed, reference images, masked editing, image-to-video, audio conditioning, aspect ratio, resolution, duration, enabled state, health, locality, quality, privacy, cost, and latency. Policies support local-first, remote-first, balanced, force-local, and force-remote. A fallback list is fixed before execution.

The shipped `mock_local` and `mock_remote_fallback` implementations are deterministic and free. They provide injectable failure and QA metadata for integration tests.

## Modality pipelines

- Copy and script use structured output contracts. Product claims are checked against the approved claim list.
- Storyboards persist versioned shots, purpose, duration, dependencies, and shot metadata.
- Images support generation, variation, and editing capability gates, references, masks, and output specifications.
- Video is shot-based. Shot plans and continuity state are persisted independently before final assembly. The current assembly adapter produces a safe manifest only because FFmpeg is not installed; it never constructs or executes a shell command.
- Audio covers general audio, voice, SFX/Foley, and music briefs. Voice generation requires a cleared voice/consent profile. Mix plans keep dialogue, music, and SFX stems distinct and include ducking instructions.
- Captions, transcripts, and audio-description drafts use structured timing/version-aware contracts. Accessibility requirements are approval gates, not optional metadata.

## Character, brand, product, and continuity

Prompt compilation includes only modality-relevant identity information. Visual work receives visual character anchors; audio receives voice/rights information; copy receives persona/tone information. Character version, brand version, and product version are recorded in provenance. QA compares observable provider metadata with required character hair, product label, and brand palette values. Video continuity state tracks subject, wardrobe, environment, lighting, props, camera direction, audio, and transition dependencies between shots.

## Asset storage and versioning

Assets are stored beneath `data/assets/generated` and provider response references beneath `data/provider_responses`. Only project-relative paths are persisted. Storage validates MIME type, extension, size, containment, and content before writing. Filenames are generated from internal asset identifiers; user filenames and traversal paths are never trusted.

Each `GeneratedAsset` has immutable `AssetVersion` rows with:

- checksum, MIME type, size, dimensions, duration, and metadata;
- parent version, change reason, repair flag, QA status, seed, and prompt hash;
- contract, recipe, provider, model, reference, and transformation provenance.

Archiving is soft. Approval is allowed only when the current version has passed QA. A deferred C2PA adapter records that credentials/signing are unavailable without claiming a signature was created.

## QA and review gates

The QA pipeline writes one run and individual results by category:

- technical integrity, safe path, checksum, size, dimensions, aspect ratio, and duration;
- structured schema;
- character consistency and video temporal continuity;
- product label/identity and approved claims;
- brand palette;
- visual risk metadata;
- copy claims;
- audio clipping;
- captions, transcript, audio description, and alt-text requirements;
- rights/consent;
- provenance completeness.

A failed required check blocks approval. A high-impact unknown creates a human-review request through the existing Rules Engine review model. Successful assets become `approved`; failed or review-bound assets remain non-approved.

## Retry, fallback, budgets, and cancellation

Attempts, provider/model versions, prompt hashes, changes, failures, and event transitions are durable. Transient typed failures retry within a configured maximum, then move to a compatible fallback model. A terminal failure uses a stable error code. Requests can set maximum attempts, cost, and duration. Cost records separate provider cost, units, GPU time, generation time, currency, and estimated/actual status.

`GenerationQueue` isolates orchestration from queue technology. `LocalGenerationQueue` is the current synchronous/local adapter. Queued work can be cancelled, and providers receive cancellation when an external running job reference exists.

## Persistence

Alembic revision `0007_generation_engine` adds:

- `provider_profiles`, `model_profiles`;
- `generation_jobs`, `generation_attempts`, `generation_events`;
- `prompt_packages`, `prompt_package_versions`;
- `generated_assets`, `asset_versions`, `asset_references`;
- `generation_qa_runs`, `generation_qa_results`;
- `generation_cost_records`, `continuity_states`;
- `storyboards`, `storyboard_shots`, `provenance_records`.

## API

The API provides preview, create/list/get/run/retry/cancel job operations; contract-first convenience endpoints for copy, image, storyboard, video, audio, and from-recipe generation; provider/model discovery; asset details, versions, provenance, approval, and archival.

The convenience routes do not bypass contract validation or QA.

## Configuration and extension

Provider and model profiles, policies, timeouts, cache behavior, maximum asset size, and allowed MIME mappings live in `configs/generation.yaml`. To add a real backend:

1. implement `BaseGenerationProvider` without placing provider details in the orchestrator;
2. register it in `ProviderRegistry`;
3. add an external model capability profile;
4. keep credentials in environment-backed runtime configuration;
5. add mock-first contract, normalization, cancellation, failure, and QA tests;
6. opt into live tests separately from the default suite.

## Verification

`tests/test_generation_engine.py` covers contract readiness, dry runs, local-first and capability selection, prompt constraints, rights checks, all supported modality families, shot/storyboard persistence, provenance and hashes, QA failures, accessibility gates, retry/fallback, cache idempotency, cancellation, versioning, assembly/mix safety, path/MIME rejection, and API flows. Existing Rules, Pattern/Recipe, Analyzer, migration, database, path, configuration, health, and interface tests provide regression coverage.
