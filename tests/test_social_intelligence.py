"""Comprehensive tests for Social Content Intelligence Engine backend and Excel export."""

import io
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from fastapi.testclient import TestClient

from backend.db.models.social_intelligence import (
    ContentAnalysisJob,
    ContentCopyAnalysis,
    ContentHookAnalysis,
    ContentNarrativeAnalysis,
    ContentTranscript,
    ContentTranscriptSegment,
    ContentVideoAnalysis,
    ContentVideoScene,
    CreativeRecommendation,
    CreatorIntelligence,
    ExcelExportJob,
)
from backend.db.models.social_inventory import SocialInventoryItem, SocialInventorySource
from backend.main import app
from backend.social_intelligence.copy_analyzer import analyze_caption, detect_cta
from backend.social_intelligence.creator_dna import aggregate_creator_dna
from backend.social_intelligence.creative_generator import (
    GenerationRequest,
    generate_creative_recommendations,
)
from backend.social_intelligence.excel_exporter import (
    SocialIntelligenceExcelExporter,
    safe_cell_value,
)
from backend.social_intelligence.hook_analyzer import (
    analyze_hooks,
    classify_hook_types,
    extract_opening_caption_sentence,
)
from backend.social_intelligence.media_handler import (
    is_safe_url,
    validate_media_url,
)
from backend.social_intelligence.storytelling_analyzer import analyze_storytelling
from backend.social_intelligence.transcriber import (
    MockTranscriber,
    TranscriptionResult,
    TranscriptSegmentData,
)
from backend.social_intelligence.video_deconstructor import (
    VideoDeconstructionResult,
    calculate_aspect_ratio,
)
from backend.db.session import session_scope
from backend.social_intelligence.worker import SocialIntelligenceWorker


@pytest.fixture
def db_session():
    with session_scope() as session:
        yield session


@pytest.fixture
def test_client(db_session):
    return TestClient(app)


@pytest.fixture
def sample_social_item(db_session):
    unique_suffix = uuid4().hex[:8]
    source = db_session.query(SocialInventorySource).filter_by(
        owner_id="local-operator", canonical_url="https://www.instagram.com/eldaheeh/"
    ).first()
    if source is None:
        source = SocialInventorySource(
            owner_id="local-operator",
            provider="apify",
            platform="instagram",
            source_url=f"https://www.instagram.com/eldaheeh_{unique_suffix}/",
            canonical_url=f"https://www.instagram.com/eldaheeh_{unique_suffix}/",
            username="eldaheeh",
            display_name="ElDa7ee7 - الدحيح",
        )
        db_session.add(source)
        db_session.flush()

    item = SocialInventoryItem(
        source_id=source.id,
        platform="instagram",
        external_id=f"ext_{uuid4().hex[:12]}",
        canonical_url=f"https://www.instagram.com/p/{uuid4().hex[:10]}/",
        content_hash=f"hash_{uuid4().hex[:12]}",
        content_type="video",
        caption="شاهد حلقة أحمد زويل من برنامج #الدحيح دلوقتي على اليوتيوب.\nرابط الحلقة في البايو",
        language="ar",
        published_at=datetime(2026, 10, 25, 12, 41, 31, tzinfo=timezone.utc),
        author={"username": "eldaheeh", "display_name": "ElDa7ee7 - الدحيح"},
        media=[
            {
                "type": "video",
                "width": 1080,
                "height": 1920,
                "duration_seconds": 88.72,
                "url": "https://example.com/mock_video.mp4",
                "url_status": "observed_temporary",
            }
        ],
        metrics={"views": 172045, "likes": 5257, "comments": 17, "shares": None, "saves": None},
        hashtags=["الدحيح"],
        provider="apify",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


# 1. Media Handling & Security Tests
def test_ssrf_prevention():
    safe, err = is_safe_url("http://127.0.0.1:8000/secret")
    assert not safe
    assert "restricted network" in err or "blocked" in err

    safe, err = is_safe_url("http://localhost:8000")
    assert not safe

    safe, err = is_safe_url("ftp://example.com/video.mp4")
    assert not safe
    assert "Unsupported URL scheme" in err

    safe, err = is_safe_url("https://www.instagram.com/p/test")
    assert safe


def test_media_url_validation_mock(monkeypatch):
    # Test accessibility probe
    res = validate_media_url("http://127.0.0.1/blocked")
    assert not res.is_accessible
    assert not res.is_expired


# 2. Transcriber Tests
def test_mock_transcriber():
    transcriber = MockTranscriber(sample_text="مرحبا بكم في الدحيح", language="ar")
    res = transcriber.transcribe(Path("dummy.wav"))
    assert res.status == "completed"
    assert res.language == "ar"
    assert len(res.segments) == 2
    assert res.segments[0].segment_index == 1
    assert "مرحبا بكم" in res.segments[0].text
    assert res.segments[0].confidence == 0.98


# 3. Hook Analysis Tests
def test_hook_classification_taxonomy():
    cats = classify_hook_types("هل تعلم سر جائزة نوبل؟", "رابط الحلقة في البايو")
    assert "question_hook" in cats
    assert "curiosity_gap" in cats

    cats_story = classify_hook_types("في يوم من الأيام حصلت المفاجأة", "")
    assert "story_opening" in cats_story
    assert "curiosity_gap" in cats_story


def test_analyze_hooks_comprehensive():
    transcript = TranscriptionResult(
        language="ar",
        language_probability=0.98,
        full_text="كيف بدأ أحمد زويل مشواره العلمي؟",
        duration_seconds=30.0,
        model_name="test-model",
        status="completed",
        segments=[
            TranscriptSegmentData(
                segment_index=1,
                start_time=0.0,
                end_time=3.5,
                text="كيف بدأ أحمد زويل مشواره العلمي؟",
                confidence=0.96,
            )
        ],
    )
    caption = "شاهد الحلقة كاملة #الدحيح\nالرابط في البايو"
    hook_res = analyze_hooks(transcript, None, caption, "أحمد زويل")

    assert hook_res.spoken_hook is not None
    assert "أحمد زويل" in hook_res.spoken_hook.exact_text
    assert hook_res.spoken_hook.start_time == 0.0
    assert hook_res.spoken_hook.end_time == 3.5
    assert "question_hook" in hook_res.hook_types
    assert hook_res.heuristic_score > 0
    assert len(hook_res.qualitative_strengths) > 0


# 4. Copywriting Analysis Tests
def test_copywriting_cta_and_dialect():
    caption = "شاهد حلقة أحمد زويل من برنامج #الدحيح دلوقتي على اليوتيوب. رابط الحلقة في البايو"
    res = analyze_caption(caption, author_name="الدحيح")

    assert res.cta_type == "link_in_bio"
    assert res.is_explicit_cta
    assert "البايو" in (res.cta_text or "")
    assert "Egyptian Dialect" in res.writing_style
    assert "الدحيح" in res.hashtag_strategy["branded_hashtags"]
    assert res.main_topic == "Science & Biography"


# 5. Storytelling Analysis Tests
def test_storytelling_narrative_stages():
    transcript = TranscriptionResult(
        language="ar",
        language_probability=0.99,
        full_text="البداية في دمنهور ثم رحلة الإسكندرية وصولا لكالتيك ونوبل. الرابط في البايو",
        duration_seconds=45.0,
        model_name="test-model",
        status="completed",
        segments=[
            TranscriptSegmentData(1, 0.0, 4.0, "البداية في دمنهور", 0.95),
            TranscriptSegmentData(2, 4.0, 15.0, "رحلة الإسكندرية للولايات المتحدة", 0.92),
            TranscriptSegmentData(3, 15.0, 35.0, "التجربة الحاسمة التي غيرت كيمياء الفيمتو", 0.94),
            TranscriptSegmentData(4, 35.0, 45.0, "شاهد الحلقة كاملة والرابط في البايو", 0.98),
        ],
    )
    story = analyze_storytelling(transcript, None, "حلقة زويل")
    assert story.narrative_pattern == "educational_explanation"
    assert len(story.stages) >= 3
    assert story.stages[0].stage_name == "Opening / Hook"
    assert story.stages[-1].stage_name == "Closing Transcript Interval"


# 6. Video Deconstruction Aspect Ratio Test
def test_aspect_ratio_calculation():
    assert calculate_aspect_ratio(1080, 1920) == "9:16 (Vertical)"
    assert calculate_aspect_ratio(1920, 1080) == "16:9 (Landscape)"
    assert calculate_aspect_ratio(1080, 1080) == "1:1 (Square)"


# 7. Creator DNA Aggregation Tests
def test_creator_dna_aggregation(db_session, sample_social_item):
    # Create an analysis job and analyses for sample_social_item
    job = ContentAnalysisJob(
        item_uuid=sample_social_item.uuid,
        status="COMPLETED",
        stage="COMPLETED",
        progress_percent=100.0,
    )
    db_session.add(job)
    db_session.flush()

    hook = ContentHookAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        hook_types=["curiosity_gap", "question_hook"],
        model_name="test-model",
    )
    copy = ContentCopyAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        main_topic="Science & Biography",
        cta_type="link_in_bio",
    )
    db_session.add_all([hook, copy])
    db_session.commit()

    intel = aggregate_creator_dna(db_session, "instagram", "eldaheeh")
    assert intel.username == "eldaheeh"
    assert intel.sample_size >= 1
    assert "curiosity_gap" in (intel.common_hook_types or [])
    assert "Science & Biography" in (intel.primary_topics or [])
    assert intel.limitations_notice is not None


# 8. AI Creative Generator Tests
def test_creative_recommendations_generation(db_session, sample_social_item):
    req = GenerationRequest(
        item_uuid=sample_social_item.uuid,
        creator_username="eldaheeh",
        output_type="hook_variations",
        topic_context="أحمد زويل",
    )
    outputs = generate_creative_recommendations(db_session, req)
    assert len(outputs) == 3
    for o in outputs:
        assert o.is_ai_generated
        assert o.suggested_hook is not None
        assert o.creative_rationale is not None


# 9. Excel 14-Sheet Workbook Validation Tests
def test_excel_export_all_14_sheets(db_session, sample_social_item):
    # Ensure job and analyses exist
    job = ContentAnalysisJob(
        item_uuid=sample_social_item.uuid,
        status="COMPLETED",
        stage="COMPLETED",
        progress_percent=100.0,
    )
    db_session.add(job)
    db_session.flush()

    t = ContentTranscript(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        language="ar",
        full_text="كيف بدأ أحمد زويل مشواره؟",
        duration_seconds=30.0,
        model_name="faster-whisper-base",
        status="completed",
    )
    db_session.add(t)
    db_session.flush()

    seg = ContentTranscriptSegment(
        transcript_id=t.id,
        segment_index=1,
        start_time=0.0,
        end_time=3.5,
        text="كيف بدأ أحمد زويل مشواره؟",
        confidence=0.97,
    )
    db_session.add(seg)

    h = ContentHookAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        spoken_hook={"exact_text": "كيف بدأ أحمد زويل مشواره؟", "start_time": 0.0, "end_time": 3.5, "duration": 3.5},
        visual_hook={"first_frame_composition": "MCU", "opening_visual_event": "Presenter entry"},
        text_hook={"opening_caption_sentence": "شاهد حلقة أحمد زويل"},
        hook_types=["question_hook", "curiosity_gap"],
        heuristic_score=8.7,
        model_name="test-hook-model",
    )
    db_session.add(h)

    c = ContentCopyAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        original_caption=sample_social_item.caption,
        opening_sentence="شاهد حلقة أحمد زويل",
        primary_message="حلقة جديدة عن أحمد زويل",
        main_topic="Science & Biography",
        cta_type="link_in_bio",
        cta_text="رابط الحلقة في البايو",
        is_explicit_cta=True,
    )
    db_session.add(c)

    n = ContentNarrativeAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        narrative_pattern="educational_explanation",
        stages=[{"stage_name": "Opening", "start_time": 0.0, "end_time": 3.5, "description": "Hook", "evidence": "text"}],
    )
    db_session.add(n)

    v = ContentVideoAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        duration=88.72,
        aspect_ratio="9:16 (Vertical)",
        width=1080,
        height=1920,
        scene_count=1,
        editing_pace="Moderate",
    )
    db_session.add(v)
    db_session.flush()

    sc = ContentVideoScene(
        video_analysis_id=v.id,
        scene_index=1,
        start_time=0.0,
        end_time=88.72,
        duration=88.72,
        visual_description="Talking head presenter",
        camera_framing="MCU",
    )
    db_session.add(sc)

    rec = CreativeRecommendation(
        item_uuid=sample_social_item.uuid,
        creator_username="eldaheeh",
        output_type="hook_variations",
        target_platform="instagram_reels",
        target_language="ar",
        suggested_hook="عارف إيه سر أحمد زويل؟",
        model_name="creative-engine-v1",
        is_ai_generated=True,
    )
    db_session.add(rec)
    db_session.commit()

    exporter = SocialIntelligenceExcelExporter(db_session)
    wb = exporter.generate_workbook(item_uuids=[sample_social_item.uuid])

    # Check that all 14 sheets exist with exact expected names
    expected_sheets = [
        "01 Executive Summary",
        "02 All Content",
        "03 Hooks",
        "04 Transcripts",
        "05 Copywriting",
        "06 Storytelling",
        "07 Video Scenes",
        "08 Video DNA",
        "09 Creator DNA",
        "10 Engagement Analytics",
        "11 AI Creative Outputs",
        "12 Errors & Processing Status",
        "13 Data Dictionary",
        "14 Methodology",
        "15 Hook Patterns",
        "16 Creator Comparisons",
        "17 Content Opportunities",
        "18 Evidence References",
    ]
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 18
    for exp in expected_sheets:
        assert exp in sheet_names

    # Check Sheet 02 has content and Arabic preserved
    ws_content = wb["02 All Content"]
    assert ws_content.max_row >= 2
    row_2_vals = [cell.value for cell in ws_content[2]]
    assert str(sample_social_item.uuid) in row_2_vals
    assert "eldaheeh" in row_2_vals

    # Check Sheet 04 has transcript
    ws_transcript = wb["04 Transcripts"]
    assert ws_transcript.max_row >= 2
    assert "كيف بدأ أحمد زويل مشواره؟" in [c.value for c in ws_transcript[2]]

    # Formula injection check
    assert safe_cell_value("=1+1") == "'=1+1"
    assert safe_cell_value("+cmd") == "'+cmd"
    assert safe_cell_value("@calc") == "'@calc"

    # Save to in-memory bytes and reload with openpyxl to ensure valid XLSX
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    reloaded_wb = openpyxl.load_workbook(stream)
    assert len(reloaded_wb.sheetnames) == len(expected_sheets)


# 10. FastAPI Endpoints Integration Tests
def test_api_endpoints_flow(test_client, sample_social_item):
    # 1. Single analysis request
    resp = test_client.post(f"/social-intelligence/analyze/{sample_social_item.uuid}")
    assert resp.status_code in {200, 202}
    data = resp.json()
    assert data["item_uuid"] == str(sample_social_item.uuid)
    job_uuid = data["uuid"]

    # 2. Get job status
    resp_job = test_client.get(f"/social-intelligence/jobs/{job_uuid}")
    assert resp_job.status_code == 200
    assert resp_job.json()["uuid"] == job_uuid

    # 3. Get complete analysis endpoint
    resp_comp = test_client.get(f"/social-intelligence/items/{sample_social_item.uuid}")
    assert resp_comp.status_code == 200
    assert resp_comp.json()["item_uuid"] == str(sample_social_item.uuid)

    # 4. Creative generation endpoint
    resp_gen = test_client.post(
        "/social-intelligence/creative/generate",
        json={
            "item_uuid": str(sample_social_item.uuid),
            "creator_username": "eldaheeh",
            "output_type": "hook_variations",
            "topic_context": "أحمد زويل",
        },
    )
    assert resp_gen.status_code == 201
    assert len(resp_gen.json()) >= 1
    assert resp_gen.json()[0]["is_ai_generated"] is True

    # 5. Creator DNA endpoint
    resp_creator = test_client.get("/social-intelligence/creators/instagram/eldaheeh")
    assert resp_creator.status_code == 200
    assert resp_creator.json()["username"] == "eldaheeh"

    # 6. Excel Export job creation endpoint
    resp_export = test_client.post(
        "/social-intelligence/exports/excel",
        json={"scope": "all_completed", "item_uuids": [str(sample_social_item.uuid)]},
    )
    assert resp_export.status_code == 201
    export_uuid = resp_export.json()["uuid"]

    # 7. Download Excel export
    resp_dl = test_client.get(f"/social-intelligence/exports/excel/{export_uuid}/download")
    assert resp_dl.status_code == 200
    assert resp_dl.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp_dl.content) > 1000

    # 8. Direct stream export
    resp_stream = test_client.get("/social-intelligence/exports/excel/stream")
    assert resp_stream.status_code == 200
    assert len(resp_stream.content) > 1000


def test_export_row_by_row_validation_against_db(db_session, sample_social_item):
    """Verify that every database record precisely matches generated Excel rows."""
    job = ContentAnalysisJob(
        item_uuid=sample_social_item.uuid,
        status="COMPLETED",
        stage="COMPLETED",
        progress_percent=100.0,
    )
    db_session.add(job)
    db_session.flush()

    h = ContentHookAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        spoken_hook={"exact_text": "هل تعلم سر جائزة نوبل؟", "start_time": 0.0, "end_time": 3.0, "duration": 3.0},
        hook_types=["question_hook", "curiosity_gap"],
        heuristic_score=8.5,
        model_name="deterministic-multilingual-nlp-v2",
        identified_hooks=[
            {
                "modality": "spoken",
                "category": "question_hook",
                "exact_text": "هل تعلم سر جائزة نوبل؟",
                "start_time": 0.0,
                "end_time": 3.0,
                "duration": 3.0,
                "mechanism": "Question Open Loop",
                "attention_strategy": "Direct Inquiry",
                "explanation": "Spoken opening inquiry",
                "subjective_assessment": "(Subjective) Strong cognitive inquiry",
                "evidence": {"verbatim_quote": "هل تعلم سر جائزة نوبل؟"},
                "confidence": 0.94,
                "suggested_alternatives": ["Alternative hook test"],
            }
        ],
    )
    c = ContentCopyAnalysis(
        job_id=job.id,
        item_uuid=sample_social_item.uuid,
        original_caption=sample_social_item.caption,
        opening_sentence="شاهد حلقة أحمد زويل",
        primary_message="حلقة جديدة عن أحمد زويل",
        main_topic="Science & Innovation",
        cta_type="link_in_bio",
        cta_text="رابط الحلقة في البايو",
        is_explicit_cta=True,
    )
    db_session.add_all([h, c])
    db_session.commit()

    exporter = SocialIntelligenceExcelExporter(db_session)
    wb = exporter.generate_workbook(item_uuids=[sample_social_item.uuid])

    # 1. Validate Sheet 03 Hooks matches DB
    ws_hooks = wb["03 Hooks"]
    assert ws_hooks.max_row >= 2
    hook_rows = list(ws_hooks.iter_rows(min_row=2, values_only=True))
    assert any(str(sample_social_item.uuid) == r[0] and "هل تعلم سر جائزة نوبل؟" in str(r[5]) for r in hook_rows)

    # 2. Validate Sheet 05 Copywriting matches DB
    ws_copy = wb["05 Copywriting"]
    assert ws_copy.max_row >= 2
    copy_rows = list(ws_copy.iter_rows(min_row=2, values_only=True))
    assert any(str(sample_social_item.uuid) == r[0] and "link_in_bio" in (r[11], r[12]) for r in copy_rows)

    # 3. Validate Sheet 18 Evidence References
    ws_ev = wb["18 Evidence References"]
    assert ws_ev.max_row >= 2
    ev_rows = list(ws_ev.iter_rows(min_row=2, values_only=True))
    assert any(str(sample_social_item.uuid) == r[0] and "هل تعلم سر جائزة نوبل؟" in str(r[5]) for r in ev_rows)


def test_multilingual_semantic_provider_evidence_grounded():
    """Verify linguistic semantic analyzer on Egyptian Arabic, MSA, and English without hardcoded creators."""
    from backend.social_intelligence.semantic_provider import get_semantic_provider
    provider = get_semantic_provider()

    # Egyptian Arabic
    egyptian_copy = "دلوقتي عشان تفهم الحكاية دي لازم تركز معايا.. الرابط كامل في البايو #تكنولوجيا"
    res_eg = provider.analyze_copy(caption=egyptian_copy, author_name="أحمد حسن")
    assert "Egyptian Dialect" in res_eg.writing_style
    assert res_eg.cta_type == "link_in_bio"
    assert res_eg.is_explicit_cta is True
    assert len(res_eg.evidence_citations) >= 1

    # Modern Standard Arabic
    msa_copy = "كيف يمكن للذكاء الاصطناعي تغيير مستقبل التعليم؟ شاركنا رأيك في التعليقات."
    res_msa = provider.analyze_copy(caption=msa_copy)
    assert "Modern Standard Arabic" in res_msa.writing_style
    assert res_msa.cta_type == "comment"

    # Hook extraction with exact timestamps
    segments = [
        {"segment_index": 1, "start_time": 0.0, "end_time": 2.5, "text": "هل تعلم ما هو أغرب سر في الكون؟"},
        {"segment_index": 2, "start_time": 2.5, "end_time": 5.0, "text": "هذا السؤال حير العلماء لعقود."},
    ]
    hooks = provider.analyze_hooks(
        transcript_segments=segments,
        full_transcript="هل تعلم ما هو أغرب سر في الكون؟ هذا السؤال حير العلماء لعقود.",
        video_metadata=None,
        caption="حلقة جديدة",
        title="أسرار الكون",
        source_duration=60.0,
    )
    assert hooks.spoken_hook is not None
    assert hooks.spoken_hook.category == "question_hook"
    assert hooks.spoken_hook.exact_text == "هل تعلم ما هو أغرب سر في الكون؟"
    assert hooks.spoken_hook.start_time == 0.0
    assert hooks.spoken_hook.end_time == 2.5
    assert len(hooks.spoken_hook.suggested_alternatives) >= 2


def test_creator_comparison_api(test_client, db_session, sample_social_item):
    """Test side-by-side comparison endpoint."""
    resp = test_client.get("/social-intelligence/creators/compare?usernames=eldaheeh&platform=instagram")
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "instagram"
    assert len(data["creators"]) >= 1
    assert "metrics_comparison" in data["comparison_matrix"]


def test_content_search_api(test_client, db_session, sample_social_item):
    """Test structured search endpoint across completed analyses."""
    # Search by platform
    resp = test_client.post(
        "/social-intelligence/search",
        json={"platform": "instagram", "limit": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert isinstance(data["results"], list)


def test_capabilities_and_cancel_api(test_client, sample_social_item):
    """Test capabilities endpoint and safe cancellation."""
    resp_cap = test_client.get("/social-intelligence/capabilities")
    assert resp_cap.status_code == 200
    cap = resp_cap.json()
    assert cap["status"] == "healthy"
    assert "cpu_cores" in cap["system"]

    fake_uuid = str(sample_social_item.uuid)
    resp_cancel = test_client.post(f"/social-intelligence/jobs/{fake_uuid}/cancel")
    assert resp_cancel.status_code == 200


def test_configurable_llm_provider_executes_and_validates_json(monkeypatch):
    """A configured provider makes an endpoint call instead of silently delegating."""
    import json
    from backend.social_intelligence.semantic_provider import ConfigurableLLMSemanticProvider

    called = {}
    payload = {
        "original_caption": "How did this happen?", "opening_sentence": "How did this happen",
        "primary_message": "Investigates an event", "main_topic": "Event investigation",
        "secondary_topics": [], "tone_of_voice": "curious", "writing_style": "concise",
        "emotional_framing": "curiosity", "persuasion_techniques": ["question"],
        "content_objective": "inform", "audience_address": "general", "hashtag_strategy": {},
        "cta_type": "none", "cta_text": None, "is_explicit_cta": False,
        "caption_structure": "question", "sentence_characteristics": "short",
        "readability_observations": "clear", "brand_voice_indicators": "not established",
        "summary": "A concise question-led caption.",
        "evidence_citations": [{"source_modality": "caption", "verbatim_quote": "How did this happen", "location_description": "opening", "confidence": 0.9}],
        "model_name": "ignored-by-adapter",
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    def fake_post(url, **kwargs):
        called["url"] = url
        return Response()

    monkeypatch.setattr("backend.social_intelligence.semantic_provider.httpx.post", fake_post)
    provider = ConfigurableLLMSemanticProvider("http://127.0.0.1:9999/v1", model_name="local-arabic-model")
    result = provider.analyze_copy(caption="How did this happen?")
    assert called["url"].endswith("/chat/completions")
    assert result.model_name == "local-arabic-model"
    assert provider.get_provider_info().last_execution == "succeeded"


def test_evidence_verifier_rejects_mismatched_quote():
    from types import SimpleNamespace
    from uuid import uuid4
    from backend.social_intelligence.evidence_verifier import build_verified_claims

    transcript = TranscriptionResult(
        language="en", language_probability=1.0, full_text="This is the exact source",
        duration_seconds=3.0, model_name="test", status="completed",
        segments=[TranscriptSegmentData(1, 0.0, 3.0, "This is the exact source", confidence=0.9)],
    )
    hook = SimpleNamespace(spoken_hook=SimpleNamespace(
        exact_text="Fabricated quotation", start_time=0.0, end_time=3.0, key_attention_trigger="question"
    ), text_hook=None)
    claims = build_verified_claims(
        item_uuid=uuid4(), transcript=transcript, caption=None, hook_result=hook,
        copy_result=SimpleNamespace(evidence_citations=[]), narrative_result=SimpleNamespace(stages=[]),
        video_result=None, provider_name="test", provider_model="test-v1",
    )
    assert claims[0].verification_status == "invalid"
