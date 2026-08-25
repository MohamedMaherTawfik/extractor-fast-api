"""Explainable deterministic Content DNA comparison and nearest neighbors."""

from numbers import Number
from typing import Any

from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.repositories.content_dna_repository import ContentDNARepository
from backend.repositories.content_repository import ContentRepository
from backend.schemas.pattern_recipe import (
    ContentClusterRequest,
    ContentClusterResponse,
    DNASimilarityResponse,
    PatternFilters,
    SimilarContentItem,
)
from backend.services.pattern_config import PatternConfig, load_pattern_config


class ContentSimilarityService:
    def __init__(self, session: Session, *, config: PatternConfig | None = None) -> None:
        self.dna = ContentDNARepository(session)
        self.content = ContentRepository(session)
        self.config = config or load_pattern_config()

    def compare(self, first_content: int | str, second_content: int | str) -> DNASimilarityResponse:
        first = self._dna_for_content(first_content)
        second = self._dna_for_content(second_content)
        return self._compare_dna(first, second)

    def _compare_dna(self, first, second) -> DNASimilarityResponse:
        section_scores = {}
        shared = {}
        different = {}
        for section in self.config.similarity_weights:
            left = _comparison_section(getattr(first, section, {}))
            right = _comparison_section(getattr(second, section, {}))
            section_scores[section], same, changed = _compare_values(left, right)
            if same:
                shared[section] = same
            if changed:
                different[section] = changed
        weights = self.config.similarity_weights
        available_weight = sum(weights[name] for name in section_scores)
        score = (
            sum(section_scores[name] * weights[name] for name in section_scores) / available_weight
            if available_weight else 0.0
        )
        first_sequence = [item["role"] for item in first.segment_sequence]
        second_sequence = [item["role"] for item in second.segment_sequence]
        return DNASimilarityResponse(
            content_id=first.content_id,
            compared_content_id=second.content_id,
            similarity_score=round(score, 6),
            shared_features=shared,
            different_features=different,
            shared_sequence=_lcs(first_sequence, second_sequence),
            timing_differences={
                "product_reveal_position": _difference(first.product.get("first_appearance_position"), second.product.get("first_appearance_position")),
                "cta_start_position": _difference(first.cta.get("start_position"), second.cta.get("start_position")),
                "average_shot_length_ms": _difference(first.editing.get("average_shot_length_ms"), second.editing.get("average_shot_length_ms")),
            },
            performance_differences=_performance_differences(first.performance, second.performance),
            weights=weights,
        )

    def similar(self, content_identifier: int | str, *, limit: int = 10) -> list[SimilarContentItem]:
        target = self._dna_for_content(content_identifier)
        candidates = self.dna.list_latest(
            PatternFilters(content_type=target.content_type)
        )
        scored = []
        for candidate in candidates:
            if candidate.content_id == target.content_id:
                continue
            comparison = self._compare_dna(target, candidate)
            scored.append((candidate.content_id, comparison.similarity_score))
        scored.sort(key=lambda item: item[1], reverse=True)
        selected = scored[:limit]
        contents = {item.id: item for item in self.content.list_by_ids([item[0] for item in selected])}
        return [
            SimilarContentItem(
                content_id=content_id,
                content_uid=contents[content_id].content_uid,
                similarity_score=score,
            )
            for content_id, score in selected
            if content_id in contents
        ]

    def cluster(self, request: ContentClusterRequest) -> list[ContentClusterResponse]:
        filters = PatternFilters.model_validate(
            request.model_dump(exclude={"similarity_threshold"})
        )
        candidates = self.dna.list_latest(filters)
        clusters: list[dict[str, Any]] = []
        for dna in sorted(candidates, key=lambda item: item.content_id):
            selected = None
            selected_score = 0.0
            for cluster in clusters:
                score = self._compare_dna(cluster["representative"], dna).similarity_score
                if score >= request.similarity_threshold and score > selected_score:
                    selected, selected_score = cluster, score
            if selected is None:
                clusters.append(
                    {
                        "representative": dna,
                        "members": [dna.content_id],
                        "similarities": [1.0],
                    }
                )
            else:
                selected["members"].append(dna.content_id)
                selected["similarities"].append(selected_score)
        return [
            ContentClusterResponse(
                cluster_id=f"CLUSTER_{index:04d}",
                representative_content_id=cluster["representative"].content_id,
                content_ids=cluster["members"],
                minimum_similarity=min(cluster["similarities"]),
            )
            for index, cluster in enumerate(clusters, 1)
        ]

    def _dna_for_content(self, identifier: int | str):
        content = (
            self.content.get(int(identifier))
            if isinstance(identifier, int) or str(identifier).isdigit()
            else self.content.get_by_uid(str(identifier))
        )
        if content is None:
            raise NotFoundError(f"Content {identifier} was not found")
        dna = self.dna.latest_for_content(content.id)
        if dna is None:
            raise NotFoundError(f"Content {identifier} has no Content DNA")
        return dna


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            output.update(_flatten(item, f"{prefix}.{key}" if prefix else key))
        return output
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def _comparison_section(value: Any) -> Any:
    ignored = {
        "content_uid",
        "creator_id",
        "published_at",
        "collected_at",
        "event_id",
        "segment_id",
        "shot_id",
        "analysis_result_id",
        "dna_uid",
    }
    if isinstance(value, dict):
        return {
            key: _comparison_section(item)
            for key, item in value.items()
            if key not in ignored
        }
    if isinstance(value, list):
        return [_comparison_section(item) for item in value]
    return value


def _compare_values(left: Any, right: Any):
    a = _flatten(left)
    b = _flatten(right)
    keys = set(a) | set(b)
    similarities = []
    shared = {}
    different = {}
    for key in keys:
        one, two = a.get(key), b.get(key)
        if one is None and two is None:
            continue
        similarity = _leaf_similarity(one, two)
        similarities.append(similarity)
        if similarity == 1:
            shared[key] = one
        else:
            different[key] = {"a": one, "b": two}
    return (sum(similarities) / len(similarities) if similarities else 0.0, shared, different)


def _leaf_similarity(one: Any, two: Any) -> float:
    if isinstance(one, Number) and isinstance(two, Number) and not isinstance(one, bool) and not isinstance(two, bool):
        scale = max(abs(float(one)), abs(float(two)), 1.0)
        return max(0.0, 1.0 - abs(float(one) - float(two)) / scale)
    if isinstance(one, list) and isinstance(two, list):
        try:
            left, right = set(map(str, one)), set(map(str, two))
        except TypeError:
            return 1.0 if one == two else 0.0
        return len(left & right) / len(left | right) if left or right else 1.0
    return 1.0 if one == two else 0.0


def _lcs(left: list[str], right: list[str]) -> list[str]:
    table = [[[] for _ in range(len(right) + 1)] for _ in range(len(left) + 1)]
    for i, a in enumerate(left, 1):
        for j, b in enumerate(right, 1):
            table[i][j] = table[i - 1][j - 1] + [a] if a == b else max(table[i - 1][j], table[i][j - 1], key=len)
    return table[-1][-1]


def _difference(one, two):
    return None if one is None or two is None else round(float(one) - float(two), 6)


def _performance_differences(first, second):
    left = first.get("normalized_metrics", {})
    right = second.get("normalized_metrics", {})
    return {
        key: _difference(left.get(key), right.get(key))
        for key in sorted(set(left) | set(right))
    }
