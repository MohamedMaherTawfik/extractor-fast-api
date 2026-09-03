import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.core.enums import (
    AnalysisRunStatus,
    ContentType,
    PatternStatus,
    PatternType,
    Platform,
    RecipeStatus,
)
from backend.db.models.content_item import ContentItem
from backend.db.session import session_scope
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import PlatformAccountRepository
from backend.schemas.analysis import AnalysisOptions
from backend.schemas.pattern_recipe import (
    PatternMineRequest,
    ContentClusterRequest,
    RecipeBuildRequest,
    RecipeVariantCreate,
    RecipeVersionCreate,
)
from backend.services.analysis_service import UniversalContentAnalyzer
from backend.services.content_dna_service import ContentDNAService
from backend.services.content_similarity_service import ContentSimilarityService
from backend.services.pattern_mining_service import PatternMiningService
from backend.services.recipe_builder_service import RecipeBuilderService
from backend.services.recipe_version_service import RecipeVersionService


SYNTHETIC = json.loads(
    Path("tests/fixtures/synthetic_pattern_contents.json").read_text(encoding="utf-8")
)


def _observations(spec: dict) -> dict:
    duration = 4000
    sequence = spec["sequence"]
    segment_size = duration // len(sequence)
    segments = [
        {
            "ref": f"segment_{index}",
            "level": "segment",
            "kind": role,
            "label": role,
            "start_ms": index * segment_size,
            "end_ms": duration if index == len(sequence) - 1 else (index + 1) * segment_size,
            "sequence_order": index,
        }
        for index, role in enumerate(sequence)
    ]
    shot_count = 4 if spec["fast"] else 2
    shot_size = duration // shot_count
    shots = [
        {
            "ref": f"shot_{index}",
            "segment_ref": "segment_0",
            "start_ms": index * shot_size,
            "end_ms": (index + 1) * shot_size,
            "sequence_order": index,
            "shot_size": "close_up" if index == 0 else "medium",
            "cut_type": "hard_cut",
        }
        for index in range(shot_count)
    ]
    product_start = 500 if spec["early_product"] else 2400
    return {
        "analysis_observations": {
            "hook_type": {
                "value": spec["hook"],
                "confidence": spec["hook_confidence"],
                "evidence": "Synthetic opening classification",
                "source": "synthetic_fixture",
                "start_ms": 0,
                "end_ms": 600,
                "target_ref": "segment_0",
            },
            "audio_energy": {
                "value": spec["audio_energy"],
                "confidence": 0.9,
                "evidence": "Synthetic normalized energy",
                "source": "synthetic_fixture",
            },
            "cta_type": {
                "value": "buy",
                "confidence": 0.9,
                "evidence": "Synthetic CTA evidence",
                "source": "synthetic_fixture",
                "start_ms": 3300,
                "end_ms": 4000,
                "target_ref": f"segment_{len(sequence) - 1}",
            },
        },
        "analysis_timeline": {
            "segments": segments,
            "shots": shots,
            "visual_events": [
                {
                    "ref": "product_event",
                    "event_type": "product_reveal",
                    "shot_ref": "shot_0" if spec["early_product"] else f"shot_{shot_count - 1}",
                    "start_ms": product_start,
                    "end_ms": product_start + 500,
                    "confidence": 0.92,
                    "evidence": "Synthetic product visibility",
                    "source": "synthetic_fixture",
                }
            ],
            "audio_events": [],
            "text_events": [],
        },
    }


def _create_analyzed(session, spec: dict, prefix: str = "synthetic", *, with_performance: bool = True):
    creator = CreatorRepository(session).create(
        {
            "display_name": f"Fictional Creator {prefix} {spec['id']}",
            "category": "education",
            "country": "EG",
            "primary_language": "en",
        }
    )
    account = PlatformAccountRepository(session).create(
        creator.id,
        {"platform": Platform.YOUTUBE, "username": f"{prefix}_{spec['id']}"},
    )
    content = ContentItem(
        content_uid=f"CNT_{prefix.upper()}_{spec['id']}",
        creator_id=creator.id,
        platform_account_id=account.id,
        platform=Platform.YOUTUBE,
        platform_content_id=f"{prefix}-{spec['id']}",
        content_type=ContentType.SHORT,
        language="en",
        duration_ms=4000,
        # Keep the synthetic comparison cohort in one publication month. Using
        # datetime.now made this fixture fail whenever a test run crossed the
        # month boundary it was originally authored around.
        published_at=datetime(2026, 8, 30, tzinfo=UTC) - timedelta(days=spec["id"]),
        views=spec["views"] if with_performance else None,
        shares=spec["shares"] if with_performance else None,
        raw_metadata=_observations(spec),
    )
    session.add(content)
    session.flush()
    run = UniversalContentAnalyzer(session).analyze_content(content.id)
    assert run.status is AnalysisRunStatus.COMPLETED
    dna = ContentDNAService(session).generate(content.id)
    return content, dna


def _dataset(session, specs=SYNTHETIC, prefix="synthetic", *, with_performance=True):
    return [
        _create_analyzed(session, spec, prefix, with_performance=with_performance)
        for spec in specs
    ]


def test_content_dna_mapping_idempotency_and_versioning() -> None:
    with session_scope() as session:
        content, first = _create_analyzed(session, SYNTHETIC[0], "dna")
        reused = ContentDNAService(session).generate(content.content_uid)
        assert reused.id == first.id
        assert first.dna_version == 1
        assert [item["role"] for item in first.segment_sequence] == [
            "HOOK", "PROBLEM", "PRODUCT_REVEAL", "PROOF", "CTA"
        ]
        assert first.product["first_appearance_position"] == 0.125
        assert first.editing["average_shot_length_ms"] == 1000
        assert first.performance["normalized_metrics"]["share_rate"] == 0.13
        assert first.provenance["evidence"]
        batch = ContentDNAService(session).generate_batch(
            [content.id, "CNT_DOES_NOT_EXIST"]
        )
        assert len(batch.items) == 1
        assert batch.failed_items[0]["content_id"] == "CNT_DOES_NOT_EXIST"

        UniversalContentAnalyzer(session).analyze_content(
            content.id, AnalysisOptions(force_reanalysis=True)
        )
        second = ContentDNAService(session).generate(content.id)
        assert second.id != first.id
        assert second.dna_version == 2


def test_pattern_layers_support_performance_evidence_and_recipe_history() -> None:
    with session_scope() as session:
        rows = _dataset(session)
        run = PatternMiningService(session).mine(
            PatternMineRequest(
                content_ids=[content.id for content, _ in rows],
                performance_metric="share_rate",
            )
        )
        assert run.contents_processed == 24
        assert run.patterns_rejected_low_support > 0
        types = {pattern.pattern_type for pattern in run.patterns}
        assert PatternType.SEQUENCE in types
        assert PatternType.TIMING in types
        assert PatternType.CROSS_MODAL in types
        assert not any(
            pattern.feature_definition.get("value") == "demonstration"
            for pattern in run.patterns
        )
        question = next(
            pattern for pattern in run.patterns
            if pattern.pattern_type is PatternType.HOOK
            and pattern.feature_definition.get("value") == "question"
        )
        assert question.support_count == 10
        assert question.status is PatternStatus.PERFORMANCE_ASSOCIATED
        assert question.performance_summary["association_only"] is True
        explained = PatternMiningService(session).explain(question.id)
        assert len(explained["evidence"]) == 10
        assert "not causation" in explained["explanation"]["causality_warning"]

        source_ids = [content.id for content, _ in rows[:10]]
        recipe = RecipeBuilderService(session).build(
            RecipeBuildRequest(
                name="Supported question recipe",
                pattern_ids=[question.id],
                content_ids=source_ids,
                content_type="short",
                platform="youtube",
            )
        )
        assert recipe.status is RecipeStatus.PROVEN
        version_one = recipe.versions[0]
        assert version_one.provenance["source_pattern_ids"] == [question.id]
        assert version_one.provenance["source_content_ids"] == source_ids
        assert version_one.evidence
        assert version_one.confidence == question.confidence

        version_two = RecipeVersionService(session).create_version(
            recipe.id,
            RecipeVersionCreate(
                payload={**version_one.payload, "hook": {"type": "statement"}},
                change_summary="Test an alternate hook family",
            ),
        )
        variant = RecipeVersionService(session).create_variant(
            recipe.id,
            RecipeVariantCreate(
                name="Earlier reveal experiment",
                changed_variables=["PRODUCT_REVEAL"],
                overrides={"product": {"first_appearance": 0.08}},
                experiment_id="EXP_SYNTHETIC_1",
            ),
        )
        reloaded = RecipeBuilderService(session).get(recipe.id)
        assert version_two.version == 2
        assert {item.version for item in reloaded.versions} == {1, 2}
        assert variant.changed_variables == ["PRODUCT_REVEAL"]
        assert reloaded.versions[0].provenance["source_pattern_ids"] == [question.id]


def test_missing_performance_low_confidence_similarity_and_insufficient_recipe() -> None:
    low_specs = []
    for index, source in enumerate(SYNTHETIC[:6], 1):
        item = {**source, "id": index, "hook_confidence": 0.3}
        low_specs.append(item)
    with session_scope() as session:
        rows = _dataset(session, low_specs, "low", with_performance=False)
        run = PatternMiningService(session).mine(
            PatternMineRequest(content_ids=[content.id for content, _ in rows])
        )
        hook = next(pattern for pattern in run.patterns if pattern.pattern_type is PatternType.HOOK)
        assert hook.status is PatternStatus.LOW_CONFIDENCE
        assert hook.performance_summary is None
        assert all(pattern.status is not PatternStatus.PERFORMANCE_ASSOCIATED for pattern in run.patterns)

        comparison = ContentSimilarityService(session).compare(rows[0][0].id, rows[1][0].id)
        assert comparison.similarity_score > 0.9
        assert comparison.shared_sequence
        similar = ContentSimilarityService(session).similar(rows[0][0].id, limit=3)
        assert len(similar) == 3
        assert similar[0].similarity_score > 0.9
        clusters = ContentSimilarityService(session).cluster(
            ContentClusterRequest(content_type="short", similarity_threshold=0.8)
        )
        assert clusters
        assert sum(len(cluster.content_ids) for cluster in clusters) == 6

        recipe = RecipeBuilderService(session).build(
            RecipeBuildRequest(
                name="Insufficient single-source plan",
                pattern_ids=[hook.id],
                content_ids=[rows[0][0].id],
            )
        )
        assert recipe.status is RecipeStatus.INSUFFICIENT_DATA
        assert recipe.versions[0].provenance["sample_size"] == 1


def test_pattern_and_recipe_api_endpoints(api_request) -> None:
    with session_scope() as session:
        rows = _dataset(session, SYNTHETIC[:5], "api")
        content_ids = [content.id for content, _ in rows]
        first_uid = rows[0][0].content_uid

    dna_response = api_request("GET", f"/content/{first_uid}/dna")
    mine_response = api_request(
        "POST", "/patterns/mine", json={"content_ids": content_ids}
    )
    assert dna_response.status_code == 200, dna_response.text
    assert mine_response.status_code == 201, mine_response.text
    patterns = mine_response.json()["patterns"]
    assert patterns
    pattern_id = patterns[0]["id"]

    detail = api_request("GET", f"/patterns/{pattern_id}")
    top = api_request("GET", "/patterns/top")
    recipe_response = api_request(
        "POST",
        "/recipes/build",
        json={
            "name": "API recipe",
            "pattern_ids": [pattern_id],
            "content_ids": content_ids,
            "content_type": "short",
        },
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["evidence"]
    assert top.status_code == 200
    assert recipe_response.status_code == 201, recipe_response.text
    recipe = recipe_response.json()
    evidence = api_request("GET", f"/recipes/{recipe['id']}/evidence")
    version = api_request(
        "POST",
        f"/recipes/{recipe['id']}/versions",
        json={"payload": recipe["versions"][0]["payload"], "change_summary": "API v2"},
    )
    variant = api_request(
        "POST",
        f"/recipes/{recipe['id']}/variants",
        json={
            "name": "Hook variant",
            "changed_variables": ["HOOK_TYPE"],
            "overrides": {"hook": {"type": "statement"}},
        },
    )
    assert evidence.status_code == 200
    assert evidence.json()["provenance"]["source_pattern_ids"]
    assert version.status_code == 201
    assert version.json()["version"] == 2
    assert variant.status_code == 201
