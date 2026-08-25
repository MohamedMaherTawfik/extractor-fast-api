"""Build editable generation plans from supported patterns without generating media."""

from collections import Counter
from statistics import mean, median
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.core.enums import EvidenceType, PatternStatus, RecipeStatus, RecipeType
from backend.core.exceptions import AnalysisError, NotFoundError
from backend.repositories.content_dna_repository import ContentDNARepository
from backend.repositories.content_repository import ContentRepository
from backend.repositories.pattern_repository import PatternRepository
from backend.repositories.recipe_repository import RecipeRepository
from backend.schemas.pattern_recipe import PatternFilters, RecipeBuildRequest
from backend.services.pattern_config import PatternConfig, load_pattern_config


class RecipeBuilderService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        config: PatternConfig | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.config = config or load_pattern_config()
        self.dna = ContentDNARepository(session)
        self.content = ContentRepository(session)
        self.patterns = PatternRepository(session)
        self.recipes = RecipeRepository(session)

    def build(self, request: RecipeBuildRequest):
        filters = PatternFilters.model_validate(
            request.model_dump(
                exclude={
                    "name", "build_mode", "pattern_ids", "content_ids", "creator_style_id",
                    "recipe_type", "metric", "minimum_sample", "target_duration_ms", "created_by",
                }
            )
        )
        if request.build_mode == "creator":
            creator_id = request.creator_style_id or request.creator_id
            if creator_id is None:
                raise AnalysisError("creator_style_id is required for creator recipes")
            filters.creator_id = creator_id
        content_ids = self._resolve_content_ids(request.content_ids)
        dnas = self.dna.list_latest(filters, content_ids=content_ids)
        patterns = self.patterns.get_many(request.pattern_ids or [])
        if request.build_mode == "top_performers":
            dnas = _top_performers(dnas, request.metric or request.performance_metric)
            linked_ids = {dna.content_id for dna in dnas}
            patterns = [
                pattern for pattern in self.patterns.list(limit=1000, top=True)
                if linked_ids & {link.content_id for link in pattern.content_links}
            ]
        elif patterns and not dnas:
            linked_ids = {link.content_id for pattern in patterns for link in pattern.content_links}
            dnas = self.dna.list_latest(content_ids=list(linked_ids))
        if not patterns and dnas:
            source_ids = {dna.content_id for dna in dnas}
            patterns = [
                pattern for pattern in self.patterns.list(limit=1000, top=True)
                if source_ids & {link.content_id for link in pattern.content_links}
            ]

        minimum_sample = request.minimum_sample or self.config.thresholds.minimum_source_contents
        sufficient = self._sufficient(dnas, patterns, minimum_sample)
        recipe_type = request.recipe_type or (
            RecipeType.CREATOR_STYLE if request.build_mode == "creator"
            else RecipeType.PROVEN_PATTERN if request.build_mode == "top_performers"
            else RecipeType.HYBRID
        )
        if not sufficient:
            recipe_type = RecipeType.EXPERIMENTAL if recipe_type is RecipeType.PROVEN_PATTERN else recipe_type
        status = RecipeStatus.PROVEN if sufficient and any(
            pattern.status is PatternStatus.PERFORMANCE_ASSOCIATED for pattern in patterns
        ) else RecipeStatus.EXPERIMENTAL
        if len(dnas) < minimum_sample:
            status = RecipeStatus.INSUFFICIENT_DATA
        confidence = mean([pattern.confidence for pattern in patterns]) if patterns else 0.0
        evidence_type = (
            EvidenceType.CORRELATED
            if any(pattern.evidence_type is EvidenceType.CORRELATED for pattern in patterns)
            else EvidenceType.OBSERVED
        )
        payload, evidence = _build_payload(dnas, patterns)
        creators = sorted({dna.identity.get("creator_id") for dna in dnas if dna.identity.get("creator_id") is not None})
        source_content_ids = sorted({dna.content_id for dna in dnas})
        source_pattern_ids = sorted({pattern.id for pattern in patterns})
        provenance = {
            "source_content_ids": source_content_ids,
            "source_pattern_ids": source_pattern_ids,
            "source_creator_ids": creators,
            "sample_size": len(source_content_ids),
            "evidence_type": evidence_type.value,
            "confidence": confidence,
            "created_by": request.created_by.value,
            "copyright_guardrail": "General characteristics only; no exact scripts, wording, or frames are copied.",
        }
        content_type = request.content_type or _mode([dna.content_type for dna in dnas]) or "other"
        platform = request.platform or _mode([dna.identity.get("platform") for dna in dnas])
        category = request.category or _mode([dna.identity.get("category") for dna in dnas])
        language = request.language or _mode([dna.identity.get("language") for dna in dnas])
        recipe = self.recipes.create(
            recipe_uid=f"REC_{uuid4().hex.upper()}",
            name=request.name,
            recipe_type=recipe_type,
            status=status,
            content_type=content_type,
            target_platform=platform,
            target_duration_ms=request.target_duration_ms or _median([dna.duration_ms for dna in dnas]),
            target_category=category,
            language=language,
            current_version=1,
            recipe_engine_version=self.settings.recipe_engine_version,
        )
        self.recipes.add_version(
            recipe,
            version=1,
            payload=payload,
            constraints={
                "minimum_source_contents": self.config.thresholds.minimum_source_contents,
                "minimum_source_creators": self.config.thresholds.minimum_source_creators,
                "minimum_confidence": self.config.thresholds.min_confidence,
                "generation_scope": "plan_only",
            },
            confidence=confidence,
            evidence_type=evidence_type,
            evidence=evidence,
            provenance=provenance,
            change_summary="Initial version built from supported Content DNA patterns",
            created_by=request.created_by,
            pattern_ids=source_pattern_ids,
            content_ids=source_content_ids,
        )
        return self.recipes.get(recipe.id)

    def list(self, **filters):
        return self.recipes.list(**filters)

    def get(self, identifier):
        recipe = self.recipes.get(identifier)
        if recipe is None:
            raise NotFoundError(f"Recipe {identifier} was not found")
        return recipe

    def evidence(self, identifier):
        recipe = self.get(identifier)
        version = max(recipe.versions, key=lambda item: item.version)
        return {
            "recipe_id": recipe.id,
            "recipe_uid": recipe.recipe_uid,
            "version": version.version,
            "why_this_recipe": version.evidence,
            "provenance": version.provenance,
            "evidence_type": version.evidence_type,
            "confidence": version.confidence,
        }

    def _resolve_content_ids(self, identifiers):
        if identifiers is None:
            return None
        result = []
        for identifier in dict.fromkeys(identifiers):
            content = (
                self.content.get(int(identifier))
                if isinstance(identifier, int) or str(identifier).isdigit()
                else self.content.get_by_uid(str(identifier))
            )
            if content is None:
                raise NotFoundError(f"Content {identifier} was not found")
            result.append(content.id)
        return result

    def _sufficient(self, dnas, patterns, minimum_sample):
        creators = {dna.identity.get("creator_id") for dna in dnas}
        return (
            len(dnas) >= max(minimum_sample, self.config.thresholds.minimum_source_contents)
            and len(creators) >= self.config.thresholds.minimum_source_creators
            and bool(patterns)
            and all(pattern.support_count >= self.config.thresholds.min_pattern_support_count for pattern in patterns)
            and mean([pattern.confidence for pattern in patterns]) >= self.config.thresholds.min_confidence
        )


def _top_performers(dnas, metric):
    if not metric:
        metric = "share_rate"
    scored = [
        (dna, dna.performance.get("normalized_metrics", {}).get(metric))
        for dna in dnas
    ]
    available = [(dna, value) for dna, value in scored if value is not None]
    available.sort(key=lambda item: item[1], reverse=True)
    count = max(1, (len(available) + 1) // 2)
    return [dna for dna, _ in available[:count]]


def _build_payload(dnas, patterns):
    sequences = [tuple(item["role"] for item in dna.segment_sequence) for dna in dnas if dna.segment_sequence]
    hooks = [dna.copy.get("hook_type") for dna in dnas]
    ctas = [dna.cta.get("type") for dna in dnas]
    payload = {
        "structure": {"segment_sequence": list(_mode(sequences) or [])},
        "hook": {"type": _mode(hooks), "duration": _median([_segment_duration(dna, "HOOK") for dna in dnas]), "style": "derived_general_pattern"},
        "segments": [{"role": role, "purpose": role.lower()} for role in (_mode(sequences) or [])],
        "visual": {"framing": _mode([_dominant_key(dna.visual.get("camera_sizes", {})) for dna in dnas]), "movement": _mode([_dominant_key(dna.visual.get("movement", {})) for dna in dnas]), "product_position": _median([dna.product.get("first_appearance_position") for dna in dnas])},
        "editing": {"average_shot_length_ms": _median([dna.editing.get("average_shot_length_ms") for dna in dnas]), "pace": _pace(dnas), "transition_strategy": _mode([_dominant_key(dna.editing.get("transitions", {})) for dna in dnas])},
        "audio": {"music_energy": _median([dna.audio.get("audio_energy") for dna in dnas]), "speech_style": "use observed family; do not copy wording"},
        "copy": {"tone": None, "dialect": None, "benefit_strategy": "use source pattern family without copying source text"},
        "product": {"first_appearance": _median([dna.product.get("first_appearance_position") for dna in dnas]), "demo_strategy": _has_role(sequences, "DEMO")},
        "cta": {"type": _mode(ctas), "timing": _median([dna.cta.get("start_position") for dna in dnas]), "strength": "pattern-derived"},
        "source_patterns": [pattern.pattern_uid for pattern in patterns],
    }
    evidence = {
        "why_this_recipe": [
            {
                "pattern_id": pattern.id,
                "name": pattern.name,
                "support": pattern.support_count,
                "support_ratio": pattern.support_ratio,
                "definition": pattern.feature_definition,
                "performance_association": pattern.performance_summary,
                "confidence": pattern.confidence,
            }
            for pattern in patterns
        ],
        "aggregate_targets": {
            "product_reveal_position": payload["product"]["first_appearance"],
            "average_shot_length_ms": payload["editing"]["average_shot_length_ms"],
            "cta_start_position": payload["cta"]["timing"],
        },
        "causality_warning": "Correlated patterns are associations and are not claimed to cause performance.",
    }
    return payload, evidence


def _mode(values):
    cleaned = [value for value in values if value is not None and value != ()]
    return Counter(cleaned).most_common(1)[0][0] if cleaned else None


def _median(values):
    cleaned = [value for value in values if value is not None]
    return median(cleaned) if cleaned else None


def _segment_duration(dna, role):
    item = next((item for item in dna.segment_sequence if item["role"] == role), None)
    return item.get("duration_ms") if item else None


def _dominant_key(counts):
    return max(counts, key=counts.get) if counts else None


def _pace(dnas):
    value = _median([dna.editing.get("average_shot_length_ms") for dna in dnas])
    if value is None:
        return None
    return "fast" if value <= 1800 else "moderate" if value <= 3500 else "slow"


def _has_role(sequences, role):
    return "include" if any(role in sequence for sequence in sequences) else None
