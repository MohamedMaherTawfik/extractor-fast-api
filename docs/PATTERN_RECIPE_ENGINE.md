# Pattern and Recipe Engine

## Flow

~~~text
Content Item
    → normalized AnalysisRun + segments/shots/events/results
    → versioned Content DNA
    → deterministic cohort-based pattern mining
    → editable, versioned generation-plan recipe
~~~

This stage creates structured plans only. It does not generate copy, images, audio, or video, and it does not implement the global Rules Engine.

## Content DNA

`ContentDNAService` maps the latest completed or partial analysis run into a machine-readable record. Each record contains identity, structure, visual, copy, audio, editing, product, CTA, behavioral, SEO, performance, provenance, functional segment sequence, and a compact feature vector.

Functional segments preserve order, duration, and normalized start/end positions. Missing measurements remain `null`; the mapper never invents unavailable shot, audio, performance, language, country, paid/organic, or creator-size data.

DNA is idempotent for an `analysis_run_id`. A new analysis run creates the next immutable `dna_version`. Provenance records analyzer, taxonomy, and pattern-engine versions plus traceable evidence references.

## Performance

`PerformanceSnapshot` supports multiple observations per content and metric, including an elapsed-minute offset suitable for T+15m, T+1h, T+24h, and later snapshots. Each value retains:

- metric name;
- raw and normalized values;
- availability;
- source and collection time;
- organic, paid, mixed, or unknown traffic classification.

The local normalizer currently derives like, comment, share, and save rates only when a positive view denominator exists. It does not treat raw views as a creative-quality score.

## Comparable Cohorts

Mining separates content by available platform, content type, category, language, country, duration bucket, traffic type, creator-size bucket, and publication month. Unknown dimensions remain explicit. A creator filter adds creator scope without splitting every general cohort by creator.

Thresholds, score weights, similarity weights, timing cutoffs, and recipe guardrails live in `configs/pattern_mining.yaml`.

## Pattern Mining

The deterministic first version mines:

- single features such as hook and CTA families;
- feature combinations;
- exact functional-segment sequences;
- timing patterns such as early product appearance;
- editing patterns such as short average shots;
- cross-modal editing-plus-audio patterns;
- scoped creator, platform, and category patterns through cohort filters.

Supported pattern types are structure, hook, visual, editing, audio, copy, CTA, product, sequence, timing, performance, and cross-modal patterns.

A pattern is persisted only when both minimum support count and ratio pass. Low-confidence source features produce `low_confidence`; they are never silently promoted. Without performance data, valid patterns remain `structural_pattern`. With comparable support and comparison metrics, they may become `performance_associated` and retain cohort medians, sample counts, and the measured difference.

### Causality warning

Performance associations are correlations. The engine never says a pattern caused an outcome unless future valid controlled-experiment evidence is supplied. `evidence_type` distinguishes observed, correlated, experimental, and inferred evidence.

The configurable pattern score combines support, source confidence, performance association, consistency, and recency. It is an operational ranking score, not scientific truth. Every pattern response includes its definition, component scores, support, confidence, linked content/evidence, and a plain causality warning.

## Similarity and Clustering

`ContentSimilarityService` compares weighted DNA sections and reports shared features, differences, shared sequence, timing differences, performance differences, weights, and the final similarity score. Content/creator identifiers and observation IDs are excluded from similarity so provenance does not masquerade as creative difference.

Clustering is lightweight and deterministic: content is assigned to a representative when its configured DNA similarity passes a requested threshold. No ML dependency is required.

## Recipes

A recipe is an editable structured generation plan, not generated content. It may describe structure, hook family, segment purposes, visual framing, editing pace, audio energy, product timing, CTA timing, and constraints.

Supported recipe types are proven pattern, creator style, platform native, category template, experimental, user defined, and hybrid. A creator-style recipe aggregates general characteristics only. It never copies exact scripts, wording, frames, or copyrighted media.

Every recipe version stores:

- source content, pattern, and creator IDs;
- source sample size;
- evidence type and confidence;
- creator (`system`, `user`, or `imported`);
- a “why this recipe” explanation;
- analyzer/pattern-derived aggregate targets and a causality warning.

Minimum content, creator, support, and confidence guardrails prevent a single item from being labeled proven. Insufficient samples return an `insufficient_data` recipe; weaker recipes remain experimental.

Recipe edits append a `RecipeVersion` and preserve all earlier versions. `RecipeVariant` records the base version, changed variables, overrides, and optional experiment ID so future A/B results can distinguish the actual changed variable.

## API

The local API provides:

- `POST /content/{content_id}/dna` and `POST /content/dna/batch`;
- `GET /content/{content_id}/dna`;
- `GET /content/{content_id}/compare/{other_content_id}`;
- `GET /content/{content_id}/similar` and `POST /content/clusters`;
- `POST /patterns/mine`, `GET /patterns`, `GET /patterns/top`, and `GET /patterns/{pattern_id}`;
- `POST /recipes/build`, `GET /recipes`, and `GET /recipes/{recipe_id}`;
- `POST /recipes/{recipe_id}/versions` and `POST /recipes/{recipe_id}/variants`;
- `GET /recipes/{recipe_id}/evidence`.

Pattern-mining and recipe-build requests accept available platform, creator, content-type, category, language, country, publication-date, duration, performance metric, and traffic-type filters. Missing dimensions are never fabricated.

## Example

A cohort may yield an observed sequence `HOOK → PROBLEM → PRODUCT_REVEAL → PROOF → CTA`, supported by 10 of 16 comparable shorts. If those ten shorts have a higher median share rate than the comparison set, the response records that association and its exact evidence IDs. A recipe can reuse the general sequence and aggregate timing ranges, while the provenance points back to those patterns and contents and explicitly avoids copying source wording.
