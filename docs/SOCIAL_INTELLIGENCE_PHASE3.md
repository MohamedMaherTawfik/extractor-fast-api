# Social Content Intelligence Phase 3

## Capability audit

Phase 2 did not execute a language model. `ConfigurableLLMSemanticProvider` delegated every method to deterministic rules while its metadata implied a configured model. The deterministic provider also described itself as genuine semantic analysis. The frame path inferred talking heads, B-roll, framing, subtitles, visible wording, camera movement, ending style, and audio/visual alignment from scene timing, edge energy, and skin-color pixels. Those conclusions were not supported by installed models.

Phase 3 keeps the deterministic provider as an explicitly labeled heuristic fallback. The OpenAI-compatible provider now performs a real `/chat/completions` request, validates JSON with Pydantic, removes ungrounded quotations and timestamps, and reports fallback execution. No approved LLM endpoint or local LLM is configured on this machine, so the acceptance run correctly reports `semantic_llm_executed: false`.

No object detector, OCR model, face detector, or vision-language model is installed. Visual output is therefore limited to FFmpeg scene boundaries and PyAV/NumPy frame statistics. Semantic visual fields remain unclassified. A Phase 2 PyAV time-base error that sampled the same frame repeatedly was fixed and verified with distinct luminance values across six scenes.

## Configured models and hardware

- Hardware: NVIDIA GeForce GTX 1070, 8 GB VRAM; CPU transcription is the validated default because CUDA runtime compatibility was not established.
- Transcription: `faster-whisper-small`, CTranslate2 INT8, CPU.
- Semantic analysis: `deterministic-multilingual-nlp-v2` heuristic fallback.
- Optional semantic model: an explicitly configured OpenAI-compatible endpoint and model name. No endpoint is enabled by default.
- Visual processing: FFmpeg scene detection plus PyAV/NumPy frame statistics. This is not semantic vision.

## Arabic transcription evaluation

Authorized sample: `data/temp_media/media_hdp1xpdl.wav`, 24.452 seconds, Arabic Instagram reel audio.

| Model | Total cached runtime | Average segment confidence | Timestamp order | Repeated phrases | WER |
| --- | ---: | ---: | --- | ---: | --- |
| base | 5.400 s | 0.569 | valid | 0 | unavailable |
| small | 13.399 s | 0.675 | valid | 0 | unavailable |

`small` improved the model confidence by 0.106 and produced more granular timestamps, so it is the configured default. Both outputs still contain obvious Arabic recognition errors and require human review. The repository has no authorized human reference transcript, so WER, dialect accuracy, and entity recall cannot be claimed. `medium` was attempted but its unauthenticated Hugging Face download remained at zero bytes and was stopped. The reproducible evaluator is `scripts/evaluate_transcription.py`; when a reference file is supplied it calculates WER, and optional entity names produce entity recall.

Raw ASR text is immutable in `raw_text`/`full_text`. Any future human or model correction belongs in `corrected_text` with a separate `correction_status`.

## Evidence verification and reliability

Each evidence record persists the content UUID, claim, evidence type, original source reference, timestamp, exact quote or metric, provider, model version, confidence, verification status, and reason. Transcript claims require exact words within overlapping timestamped segments. Caption claims require an exact normalized substring. Frame claims may contain calculated statistics only. Missing evidence is `unsupported`; quotation or timestamp mismatches are `invalid`.

Jobs now persist component-level completion, quality checks, model-specific resource usage, configurable media budgets, batch limits, retry limits, and partial status. The acceptance job processed one selected UUID only. It produced 9 verified claims, 4 transcript-backed claims requiring human review, zero invalid claims, zero unsupported claims, ten transcript segments, and six frame samples.

## Acceptance result

- Source UUID: `24ae3726-93ff-48c0-a79a-02cc5c43c8d5`
- Latest job UUID: `eca7d1a0-b312-4ead-920f-6ae91c37b1e0`
- Transcript: preserved as raw `faster-whisper-small` output; average confidence 0.669; WER unavailable.
- Spoken hook: exact opening ASR words and timestamp were verified, but hook classification remains explicitly heuristic.
- Caption: opening and CTA evidence match the stored original caption.
- Narrative: stage intervals and quotes match transcript segments; rhetorical roles are explicitly heuristic, and no payoff is asserted.
- Visual: six scene intervals contain distinct frame statistics. Talking head, B-roll, OCR, framing, action, and A/V alignment are not asserted.
- Creator DNA: existing contributing post UUID references remain intact.
- Excel: 18 sheets, 13 evidence rows, 10 transcript rows, no formula error cells; evidence rows reconcile to the latest persisted job. Four ASR-backed rows are marked `needs_review`.

## Phase 2 to Phase 3

| Area | Phase 2 | Phase 3 |
| --- | --- | --- |
| LLM provider | Silently returned deterministic output | Executes configured endpoint; structured validation; explicit fallback |
| Deterministic analysis | Presented as genuine semantic reasoning | Labeled heuristic in API, jobs, methodology, and evidence |
| Visual analysis | Unsupported semantic inferences from pixels | Scene boundaries and frame statistics only |
| Transcription | Hard-coded `base`; raw/corrected not distinguished | Configurable model; `small` selected; raw and correction fields separated |
| Evidence | Ad hoc nested quotations with hard-coded confidence/model labels | Persisted claim-level ledger with verification status |
| Completion | Media availability could produce `COMPLETED` despite missing components | Component-level completion and `PARTIAL` reporting |
| Excel | Evidence rows rebuilt from analysis fields with hard-coded model names | Sheet 18 exports persisted evidence and model metadata; legacy rows are unsupported |

## Remaining blockers

- No human reference transcript is available, so WER and true dialect/entity accuracy remain unmeasured.
- The selected `small` transcript is still not publication quality.
- No approved or installed semantic LLM is configured, so genuine model interpretation was not run in acceptance.
- No semantic computer-vision or OCR model is installed.
- The GTX 1070 has adequate nominal VRAM for larger quantized models, but CUDA libraries and a larger Whisper download must be validated before enabling GPU or selecting `medium`.

## Phase 3 changed files

- `backend/core/config.py`
- `backend/db/migrations.py`
- `backend/db/models/__init__.py`
- `backend/db/models/social_intelligence.py`
- `backend/social_intelligence/api.py`
- `backend/social_intelligence/evidence_verifier.py`
- `backend/social_intelligence/excel_exporter.py`
- `backend/social_intelligence/hook_analyzer.py`
- `backend/social_intelligence/schemas.py`
- `backend/social_intelligence/semantic_provider.py`
- `backend/social_intelligence/transcriber.py`
- `backend/social_intelligence/video_deconstructor.py`
- `backend/social_intelligence/worker.py`
- `configs/app.yaml`
- `database/migrations/versions/0016_verified_ai_evidence.py`
- `frontend/src/features/social-inventory/components/ContentAnalysisView.tsx`
- `frontend/src/features/social-inventory/intelligenceTypes.ts`
- `scripts/evaluate_transcription.py`
- `tests/test_migrations.py`
- `tests/test_social_intelligence.py`
- `docs/SOCIAL_INTELLIGENCE_PHASE3.md`
