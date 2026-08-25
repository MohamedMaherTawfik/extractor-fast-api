import hashlib
import json
from pathlib import Path

from backend.analyzers.engine import AnalysisEngine
from backend.analyzers.registry import AnalysisEngineRegistry
from backend.analyzers.router import ContentRouter
from backend.analyzers.rules import AnalysisRuleCatalog
from backend.core.config import get_settings
from backend.core.enums import (
    AnalysisModality,
    AnalysisResultStatus,
    AnalysisRunStatus,
    AnalysisStatus,
    ContentType,
    Platform,
)
from backend.db.models.analysis import AnalysisResult, AnalysisRun
from backend.db.models.content_item import ContentItem
from backend.db.session import session_scope
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import PlatformAccountRepository
from backend.schemas.analysis import AnalysisBatchRequest, AnalysisOptions
from backend.services.analysis_service import UniversalContentAnalyzer


FIXTURES = Path("tests/fixtures")


def evidence_fixture() -> dict:
    return json.loads(
        (FIXTURES / "analysis_evidence.json").read_text(encoding="utf-8")
    )


def create_content(
    session,
    content_type: ContentType,
    suffix: str,
    *,
    raw_metadata: dict | None = None,
    local_media: bool = False,
) -> ContentItem:
    creator = CreatorRepository(session).create(
        {"display_name": f"Analysis Creator {suffix}"}
    )
    account = PlatformAccountRepository(session).create(
        creator.id,
        {"platform": Platform.YOUTUBE, "username": f"analysis_{suffix}"},
    )
    content = ContentItem(
        content_uid=f"CNT_ANALYSIS_{suffix.upper()}",
        creator_id=creator.id,
        platform_account_id=account.id,
        platform=Platform.YOUTUBE,
        platform_content_id=f"analysis-{suffix}",
        content_type=content_type,
        caption="Observable fixture caption",
        duration_ms=4000,
        content_hash=hashlib.sha256(suffix.encode()).hexdigest(),
        raw_metadata=raw_metadata,
        local_media_path=(
            "tests/fixtures/sample_analysis_media.txt" if local_media else None
        ),
    )
    session.add(content)
    session.flush()
    return content


def routed_content(content_type: ContentType) -> ContentItem:
    return ContentItem(
        content_uid=f"ROUTE_{content_type.value}",
        creator_id=1,
        platform=Platform.OTHER,
        content_type=content_type,
        caption="text",
    )


def test_video_image_audio_text_and_carousel_routing() -> None:
    router = ContentRouter()
    video = router.route(routed_content(ContentType.VIDEO))
    image = router.route(routed_content(ContentType.IMAGE))
    audio = router.route(routed_content(ContentType.AUDIO))
    text = router.route(routed_content(ContentType.POST))
    carousel = router.route(routed_content(ContentType.CAROUSEL))

    assert {AnalysisModality.VIDEO, AnalysisModality.AUDIO, AnalysisModality.TEXT} <= set(
        video.modalities
    )
    assert AnalysisModality.IMAGE in image.modalities
    assert AnalysisModality.AUDIO in audio.modalities
    assert text.modalities == {
        AnalysisModality.METADATA,
        AnalysisModality.TEXT,
    }
    assert {AnalysisModality.CAROUSEL, AnalysisModality.IMAGE} <= set(
        carousel.modalities
    )


def test_rule_catalog_filters_by_modality_and_accepts_generic_new_fields() -> None:
    settings = get_settings()
    catalog = AnalysisRuleCatalog().load(
        settings.analysis_rules_file,
        settings.analysis_taxonomy_file,
    )
    rules = catalog.select(["RULE_VIDEO_HOOK", "RULE_AUDIO_ENERGY"])

    assert rules[0].applies_to_modalities({AnalysisModality.VIDEO})
    assert not rules[0].applies_to_modalities({AnalysisModality.IMAGE})
    assert rules[1].engine == "audio"
    assert catalog.rules_version == "1.0.0"
    assert catalog.taxonomy_version == "1.0.0"


def test_end_to_end_video_analysis_persists_timeline_results_and_evidence() -> None:
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.VIDEO,
            "video_e2e",
            raw_metadata=evidence_fixture(),
            local_media=True,
        )
        run = UniversalContentAnalyzer(session).analyze_content(content.content_uid)

        assert run.status is AnalysisRunStatus.COMPLETED
        assert content.analysis_status is AnalysisStatus.COMPLETED
        assert run.results_count == 10
        assert len(run.segments) == 2
        assert len(run.shots) == 2
        assert len(run.visual_events) == 1
        assert len(run.audio_events) == 1
        assert len(run.text_events) == 2

        hook = session.query(AnalysisResult).filter_by(field="hook_type").one()
        ocr = session.query(AnalysisResult).filter_by(field="ocr_text").one()
        behavior = session.query(AnalysisResult).filter_by(field="need_state").one()
        colors = session.query(AnalysisResult).filter_by(field="dominant_colors").one()

        assert hook.value == "question"
        assert hook.segment_id is not None
        assert hook.evidence
        assert colors.value == ["#112233", "#EEDDCC"]
        assert ocr.value == "UNKNOWN"
        assert ocr.manual_review is True
        assert behavior.status is AnalysisResultStatus.LOW_CONFIDENCE
        assert behavior.accepted is False
        assert behavior.evidence
        assert not {"views", "likes", "shares", "saves"} & {
            result.field for result in run.results
        }


def test_not_applicable_unknown_and_rules_subset_are_normalized() -> None:
    observations = {
        "analysis_observations": {
            "dominant_colors": {
                "value": ["#000000"],
                "confidence": 0.9,
                "evidence": "Single image palette",
            }
        }
    }
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.IMAGE,
            "image_rules",
            raw_metadata=observations,
        )
        run = UniversalContentAnalyzer(session).analyze_content(
            content.id,
            AnalysisOptions(
                rules_subset=[
                    "RULE_METADATA_DURATION",
                    "RULE_VIDEO_HOOK",
                    "RULE_DOMINANT_COLORS",
                    "RULE_OCR_TEXT",
                ]
            ),
        )
        results = {result.field: result for result in run.results}

        assert results["hook_type"].value == "NOT_APPLICABLE"
        assert results["hook_type"].accepted is True
        assert results["ocr_text"].value == "UNKNOWN"
        assert results["ocr_text"].low_confidence is True
        assert results["dominant_colors"].accepted is True
        assert run.results_count == 4


def test_analysis_modes_limit_engines_without_changing_router_core() -> None:
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.VIDEO,
            "visual_mode",
            raw_metadata=evidence_fixture(),
        )
        run = UniversalContentAnalyzer(session).analyze_content(
            content.id,
            AnalysisOptions(mode="visual_only"),
        )

        assert {result.engine for result in run.results} <= {
            "metadata",
            "video_structure",
            "vision",
            "ocr",
        }
        assert "audio" not in {result.engine for result in run.results}


class FailingVisionEngine(AnalysisEngine):
    name = "vision"
    version = "failing-test-1"

    def analyze(self, content, rules):
        raise RuntimeError("fixture engine failure")


def test_failed_engine_marks_partial_without_discarding_other_results() -> None:
    engines = AnalysisEngineRegistry()
    engines.register(FailingVisionEngine())
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.IMAGE,
            "partial",
            raw_metadata=evidence_fixture(),
        )
        run = UniversalContentAnalyzer(session, engines=engines).analyze_content(
            content.id
        )

        assert run.status is AnalysisRunStatus.PARTIAL
        assert content.analysis_status is AnalysisStatus.PARTIAL
        assert any(error["component"] == "vision" for error in run.errors)
        assert any(result.engine == "metadata" for result in run.results)
        vision_results = [result for result in run.results if result.engine == "vision"]
        assert vision_results
        assert all(
            result.status is AnalysisResultStatus.FAILED
            for result in vision_results
            if result.value != "NOT_APPLICABLE"
        )


def test_cache_streaming_hash_force_reanalysis_and_versioning() -> None:
    expected_hash = hashlib.sha256(
        (FIXTURES / "sample_analysis_media.txt").read_bytes()
    ).hexdigest()
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.VIDEO,
            "cache",
            raw_metadata=evidence_fixture(),
            local_media=True,
        )
        service = UniversalContentAnalyzer(session)
        first = service.analyze_content(content.id)
        cached = service.analyze_content(content.id)
        forced = service.analyze_content(
            content.id,
            AnalysisOptions(force_reanalysis=True),
        )

        assert first.media_hash == expected_hash
        assert cached.id == first.id
        assert forced.id != first.id
        assert forced.cache_key == first.cache_key
        assert first.analyzer_version == "1.0.0"
        assert first.rules_version == "1.0.0"
        assert first.taxonomy_version == "1.0.0"
        assert "vision:" in first.model_version


def test_batch_analysis_shares_batch_id_and_persists_across_sessions() -> None:
    with session_scope() as session:
        text = create_content(session, ContentType.POST, "batch_text")
        audio = create_content(session, ContentType.AUDIO, "batch_audio")
        runs = UniversalContentAnalyzer(session).analyze_batch(
            AnalysisBatchRequest(
                content_ids=[text.content_uid, audio.id],
                rules_subset=["RULE_METADATA_DURATION", "RULE_MAIN_TOPIC"],
            )
        )
        run_ids = [run.id for run in runs]

        assert len({run.batch_uid for run in runs}) == 1
        assert runs[0].batch_uid.startswith("ANB_")
        assert all(run.status is AnalysisRunStatus.COMPLETED for run in runs)

    with session_scope() as session:
        stored = session.query(AnalysisRun).filter(AnalysisRun.id.in_(run_ids)).all()
        assert len(stored) == 2
        assert all(run.results_count == 2 for run in stored)


def test_content_analysis_bundle_contains_traceable_entities() -> None:
    with session_scope() as session:
        content = create_content(
            session,
            ContentType.VIDEO,
            "bundle",
            raw_metadata=evidence_fixture(),
        )
        service = UniversalContentAnalyzer(session)
        run = service.analyze_content(content.id)
        bundle = service.get_content_analysis(content.content_uid)

        assert bundle.run.id == run.id
        assert len(bundle.segments) == 2
        assert len(bundle.shots) == 2
        assert bundle.text_events[1].bounding_box is not None
        hook = next(result for result in bundle.results if result.field == "hook_type")
        assert hook.segment_id is not None


def test_analysis_api_content_batch_job_and_results(api_request) -> None:
    with session_scope() as session:
        first = create_content(session, ContentType.POST, "api_first")
        second = create_content(session, ContentType.AUDIO, "api_second")
        first_uid = first.content_uid
        second_id = second.id

    response = api_request(
        "POST",
        f"/analysis/content/{first_uid}",
        json={"rules_subset": ["RULE_METADATA_DURATION", "RULE_MAIN_TOPIC"]},
    )
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "completed"

    job_response = api_request("GET", f"/analysis/jobs/{job['job_uid']}")
    result_response = api_request("GET", f"/analysis/content/{first_uid}")
    batch_response = api_request(
        "POST",
        "/analysis/batch",
        json={
            "content_ids": [second_id],
            "rules_subset": ["RULE_METADATA_DURATION"],
        },
    )

    assert job_response.status_code == 200
    assert result_response.status_code == 200
    assert len(result_response.json()["results"]) == 2
    assert batch_response.status_code == 201
    assert batch_response.json()[0]["batch_uid"].startswith("ANB_")
