# Global Rules Engine

## Boundary and flow

~~~text
Control Dictionary / Master Sheet (authoring only)
    → preview, classification, validation, normalization
    → Rule Compiler
    → versioned Rule Registry in SQLite
    → Rule Set composition + effective-date/scope selection
    → safe condition evaluation (TRUE / FALSE / UNKNOWN)
    → dependency ordering + conflict resolution
    → auditable decision and human-review requests
    → immutable, versioned Generation Contract
~~~

The engine produces decisions and requirements. It does not generate copy, images, audio, or video; invoke an AI provider; publish content; or own inventory, pricing, accounting, sales, CRM, or customer-service state. External business data is read-only context.

Excel is never queried during normal evaluation. The English master sheet, when available, is the canonical machine import contract. Arabic labels are localization/UI reference data and do not create a second runtime rule model. No master sheet is currently present; the importer returns `MASTER_CONTROL_FILE_NOT_FOUND` and remains ready for a later project-relative file.

## Rule model and lifecycle

A stable `Rule` owns one or more immutable `RuleVersion` records. New versions supersede rather than overwrite history. Versions can be `draft`, `active`, `retired`, `disabled_undefined`, or `non_executable`, and can have effective start/end times. High-impact activation requires an explicit approval flag and approver. Generated drafts never activate themselves.

Rule kinds cover hard/soft constraints, validation, transformation, recommendation, warnings, QA, accessibility, brand, character, platform, rights, factual, AI-safety, recipe, generation, technical, and policy decisions. `hardness`, `severity`, and numeric `priority` are independent:

- hard rules cannot be silently ignored;
- severity describes impact;
- priority resolves competing applicable requirements, using configurable tiers in `configs/rules.yaml`.

Rule sources retain control IDs and references for master sheets, users, the system, platform/brand/character profiles, legal policies, accessibility standards, and generated drafts. Time-sensitive policy rules retain `last_verified_at` and a stale-policy action.

## Scope and context

Scopes may constrain project, brand, character, product, platform, content type, language, country, category, campaign, recipe type, workflow stage, risk, or paid/organic status. `RuleScopeMatcher` returns `APPLICABLE`, `NOT_APPLICABLE`, or `PARTIAL_CONTEXT`.

The context supports project/task/command, content and platform profiles, explicit brand/character versions, product and Recipe data, Content DNA, audience and locale, accessibility/rights/risk profiles, performance context, user/system constraints, evidence, and read-only external context. A stable context hash excludes evaluation timestamps and combines with the active registry fingerprint, selected rule sets, stage, and Recipe version for deterministic idempotency.

## Safe conditions and three-valued logic

Conditions are structured trees with nested `all`, `any`, and `not`. Leaves allow only `EQ`, `NEQ`, `GT`, `GTE`, `LT`, `LTE`, `IN`, `NOT_IN`, `EXISTS`, `NOT_EXISTS`, `CONTAINS`, and named `MATCHES_ALLOWED_PATTERN`. Field paths pass through approved context roots and mapping-only traversal. Arbitrary attributes and dunder paths are rejected. Python `eval` and `exec` are never used.

Missing, `UNKNOWN`, `NOT_APPLICABLE`, and `MISSING_REQUIRED` are distinct. Comparisons against missing data produce `UNKNOWN`; they do not become false or pass. Low-confidence fields are also unknown when their `_confidence` entry is below the rule threshold. Rights, facts, identity, safety, and required accessibility fail closed into review/blocking behavior. Evidence-aware rules return `REQUIRE_EVIDENCE` rather than inventing facts, prices, claims, or permissions.

## Actions, conflicts, and dependencies

Actions are a controlled enum: pass, warn, block, require field/evidence, set constraint/default, recommend, rewrite, retry/regenerate, human review, omit field, downgrade claim, use fallback, and disable feature.

Dependencies are topologically ordered. Any cycle rejects the executable set with `RULE_DEPENDENCY_CYCLE`. Conflicting constraints resolve by hardness and configured numeric priority, never load order. Equal-priority hard conflicts return `CONFLICT_REQUIRES_RESOLUTION` and create human-review work rather than choosing randomly.

Rule sets are independently versioned collections with priority and safe activation criteria. Evaluation can compose global, brand, character, platform, Recipe, accessibility, locale, and other sets.

## Recipe validation and generation readiness

`RecipeRuleValidationService` injects the selected immutable Recipe version into context. Normalization deep-copies the Recipe, applies safe defaults, records constraints, and omits only explicitly optional invalid fields; it never mutates the source Recipe.

Readiness is one of `READY`, `NOT_READY`, or `HUMAN_REVIEW`, with blockers, warnings, missing fields/evidence, and conflicts. The versioned Generation Contract freezes the Recipe version, registry version, context hash, requirements, constraints, forbidden changes, evidence/accessibility/rights/technical/copy/visual/audio/QA/model requirements, approval gates, warnings, and evaluation reference. Changing an approved contract creates a new version, preserving reproducibility.

## Overrides, review, and audit

Overrides are scoped, approved, reasoned, effective-dated, expiring records; they never modify the rule. `non_overridable` hard rules reject overrides. Block, activate, retire, override, and human-review decisions are recorded through evaluation and audit tables. Logs and audit details do not require secrets or raw personal data.

The engine reports checks under the recorded rules/context. It does not claim legal compliance merely because configured checks passed.

## Master-control import

Import first returns a preview containing new, modified, unchanged, disabled, undefined, executable-candidate, and non-executable counts. Every row receives an explicit classification. `NEEDS_DEFINITION` (including an undefined `K-ROLL`) becomes `DISABLED_UNDEFINED`; `INTEGRATION_ONLY` remains context integration and never becomes creative business logic. Incomplete descriptive rows become `NON_EXECUTABLE_CONTROL`. File hashes make identical imports idempotent, while changed controls append control and draft Rule versions rather than overwriting active history.

## API

- `GET/POST /rules`, `GET /rules/{id}`, version create/activate/retire endpoints;
- `GET/POST /rule-sets`, `GET /rule-sets/{id}`;
- `POST /rules/evaluate`, `POST /rules/validate-recipe`, and `POST /rules/normalize-recipe`;
- `GET /rules/evaluations/{id}` and `/explain`;
- `POST /generation-contracts/build` and `GET /generation-contracts/{id}`;
- `POST /rule-imports/master-controls`, `POST /rule-overrides`, and human-review decisions.

## Machine schema examples

### Rule

```json
{"rule_code":"CAPTIONS_REQUIRED","domain":"accessibility","rule_type":"accessibility","hardness":"hard","severity":"high","priority":300,"scope":{"content_type":"video"},"condition":{"all":[{"field":"recipe.content_has_speech","operator":"EQ","value":true},{"field":"recipe.captions","operator":"NEQ","value":true}]},"action":{"type":"require_field","target":"recipe.captions","value":true},"message":"Captions are required","version":1,"status":"active"}
```

### RuleSet

```json
{"set_code":"VIDEO_ACCESSIBILITY","version":1,"priority":300,"activation_criteria":{"field":"content_type","operator":"EQ","value":"video"},"rule_codes":["CAPTIONS_REQUIRED"],"status":"active"}
```

### RuleEvaluationContext

```json
{"project_id":"PRJ_TEST","command":"generate","content_type":"video","platform":"instagram","recipe":{"id":1,"version":2,"content_has_speech":true,"captions":false},"character":{"id":"EMY_TEST","version":3},"brand":{"id":"MASA_TEST","version":2},"rights":{"status":"UNKNOWN"},"_confidence":{"character.hair.color":0.92},"evidence":{}}
```

### RuleEvaluationResult

```json
{"evaluation_uid":"EVAL_hash","status":"not_ready","rule_code":"CAPTIONS_REQUIRED","rule_version":1,"result":"block","action":"require_field","affected_fields":["recipe.captions"],"original_value":false,"suggested_value":true,"human_review_required":false}
```

### GenerationContract

```json
{"contract_uid":"GCON_id","version":1,"recipe_id":1,"recipe_version":2,"brand_version":2,"character_version":3,"rule_registry_version":"hash","hard_constraints":[],"soft_constraints":[],"accessibility_requirements":[],"rights_requirements":[],"human_approval_gates":[],"rule_evaluation_id":"EVAL_hash"}
```

### RuleOverride

```json
{"override_uid":"OVR_id","rule_code":"SOFT_STYLE","scope":{"campaign":"TEST"},"reason":"Approved experiment","requested_by":"tester","approved_by":"reviewer","effective_from":"2026-08-19T00:00:00Z","effective_to":"2026-08-26T00:00:00Z"}
```

### HumanReviewRequest

```json
{"review_uid":"REVIEW_id","evaluation_uid":"EVAL_hash","rule_code":"CHARACTER_LOCK","reason":"Equal-priority hard conflict","severity":"high","status":"pending","decision":null}
```
