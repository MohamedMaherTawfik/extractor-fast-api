"""Asynchronous background worker for Social Content Intelligence analysis jobs."""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.base import utc_now
from backend.db.models.social_intelligence import (
    ContentAnalysisJob,
    ContentCopyAnalysis,
    ContentHookAnalysis,
    ContentNarrativeAnalysis,
    ContentTranscript,
    ContentTranscriptSegment,
    ContentVideoAnalysis,
    ContentVideoScene,
)
from backend.db.models.social_inventory import SocialInventoryItem
from backend.db.session import session_scope
from backend.social_intelligence.copy_analyzer import analyze_caption
from backend.social_intelligence.creator_dna import aggregate_creator_dna
from backend.social_intelligence.hook_analyzer import analyze_hooks
from backend.social_intelligence.media_handler import (
    cleanup_temp_file,
    download_media_to_temp,
    validate_media_url,
)
from backend.social_intelligence.storytelling_analyzer import analyze_storytelling
from backend.social_intelligence.transcriber import (
    FasterWhisperTranscriber,
    MockTranscriber,
    TranscriberProtocol,
    extract_audio,
)
from backend.social_intelligence.video_deconstructor import deconstruct_video

logger = logging.getLogger(__name__)


class SocialIntelligenceWorker:
    """ThreadPool background worker processing content intelligence jobs asynchronously."""

    def __init__(self, max_workers: int = 2, use_mock_transcriber: bool = False) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="social-intel")
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()
        self._closed = False
        self._transcriber: TranscriberProtocol = (
            MockTranscriber() if use_mock_transcriber else FasterWhisperTranscriber(model_size="base")
        )

    def set_transcriber(self, transcriber: TranscriberProtocol) -> None:
        self._transcriber = transcriber

    def enqueue(self, job_uuid: UUID | str) -> None:
        """Enqueue a job for background processing."""
        job_id_str = str(job_uuid)
        with self._lock:
            if self._closed:
                self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="social-intel")
                self._closed = False
            current = self._futures.get(job_id_str)
            if current is not None and not current.done():
                return
            self._futures[job_id_str] = self._executor.submit(self._execute_job, job_id_str)

    def _execute_job(self, job_id_str: str) -> None:
        logger.info("Starting background analysis for job %s", job_id_str)
        temp_video_path: Path | None = None
        temp_audio_path: Path | None = None

        with session_scope() as session:
            job = session.query(ContentAnalysisJob).filter_by(uuid=UUID(job_id_str)).one_or_none()
            if job is None:
                logger.error("Job %s not found in database", job_id_str)
                return

            item = session.query(SocialInventoryItem).filter_by(uuid=job.item_uuid).one_or_none()
            if item is None:
                job.status = "FAILED"
                job.stage = "FAILED"
                job.error_category = "ITEM_NOT_FOUND"
                job.error_message = f"Social inventory item {job.item_uuid} not found"
                job.completed_at = utc_now()
                return

            job.status = "PROCESSING"
            job.stage = "VALIDATING_MEDIA"
            job.progress_percent = 10.0
            job.started_at = utc_now()
            session.flush()

            # Inspect media
            media_list = item.media or []
            video_url = None
            known_duration = None
            for m in media_list:
                if isinstance(m, dict) and m.get("type") == "video" and m.get("url"):
                    video_url = m["url"]
                    known_duration = m.get("duration_seconds")
                    break

            media_available = False
            transcript_res = None
            video_decomp_res = None

            if video_url:
                validation = validate_media_url(video_url)
                if validation.is_accessible:
                    try:
                        job.stage = "ACQUIRING_MEDIA"
                        job.progress_percent = 25.0
                        session.flush()
                        temp_video_path = download_media_to_temp(video_url)
                        media_available = True
                    except Exception as exc:
                        logger.warning("Failed to download media for job %s: %s", job_id_str, exc)
                        media_available = False
                else:
                    logger.info("Media URL for job %s is not accessible: %s", job_id_str, validation.error_message)

            # Stage 2: Audio extraction and transcription
            if media_available and temp_video_path:
                job.stage = "TRANSCRIBING"
                job.progress_percent = 40.0
                session.flush()
                audio_ext = extract_audio(temp_video_path)
                if audio_ext.has_audio and audio_ext.audio_path:
                    temp_audio_path = audio_ext.audio_path
                    try:
                        transcript_res = self._transcriber.transcribe(temp_audio_path)
                    except Exception as exc:
                        logger.error("Transcriber threw an unexpected exception: %s", exc)

            # Stage 3: Video deconstruction
            if media_available and temp_video_path:
                job.stage = "DECONSTRUCTING_VIDEO"
                job.progress_percent = 60.0
                session.flush()
                try:
                    video_decomp_res = deconstruct_video(temp_video_path, known_duration=known_duration)
                except Exception as exc:
                    logger.error("Video deconstruction threw an exception: %s", exc)

            # Stage 4: Copywriting analysis
            job.stage = "ANALYZING_COPY"
            job.progress_percent = 75.0
            session.flush()
            author_info = item.author or {}
            author_name = author_info.get("display_name") or author_info.get("username")
            copy_res = analyze_caption(item.caption, author_name=author_name)

            # Stage 5: Hook analysis
            job.stage = "EXTRACTING_HOOKS"
            job.progress_percent = 85.0
            session.flush()
            hook_res = analyze_hooks(transcript_res, video_decomp_res, item.caption, item.title)

            # Stage 6: Storytelling analysis
            job.stage = "ANALYZING_STORYTELLING"
            job.progress_percent = 92.0
            session.flush()
            story_res = analyze_storytelling(transcript_res, video_decomp_res, item.caption)

            # Persist all results
            # Clean up previous records for this job if retrying
            session.query(ContentTranscript).filter_by(job_id=job.id).delete()
            session.query(ContentHookAnalysis).filter_by(job_id=job.id).delete()
            session.query(ContentCopyAnalysis).filter_by(job_id=job.id).delete()
            session.query(ContentNarrativeAnalysis).filter_by(job_id=job.id).delete()
            session.query(ContentVideoAnalysis).filter_by(job_id=job.id).delete()

            # Transcript
            if transcript_res and transcript_res.full_text:
                transcript_db = ContentTranscript(
                    job_id=job.id,
                    item_uuid=item.uuid,
                    language=transcript_res.language,
                    language_probability=transcript_res.language_probability,
                    full_text=transcript_res.full_text,
                    duration_seconds=transcript_res.duration_seconds,
                    model_name=transcript_res.model_name,
                    status=transcript_res.status,
                )
                session.add(transcript_db)
                session.flush()
                for seg in transcript_res.segments:
                    seg_db = ContentTranscriptSegment(
                        transcript_id=transcript_db.id,
                        segment_index=seg.segment_index,
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        text=seg.text,
                        speaker=seg.speaker,
                        confidence=seg.confidence,
                    )
                    session.add(seg_db)

            # Hook analysis
            hook_db = ContentHookAnalysis(
                job_id=job.id,
                item_uuid=item.uuid,
                spoken_hook=asdict(hook_res.spoken_hook) if hook_res.spoken_hook else None,
                visual_hook=asdict(hook_res.visual_hook) if hook_res.visual_hook else None,
                text_hook=asdict(hook_res.text_hook) if hook_res.text_hook else None,
                hook_types=hook_res.hook_types,
                clarity=hook_res.clarity,
                specificity=hook_res.specificity,
                relevance=hook_res.relevance,
                curiosity_mechanism=hook_res.curiosity_mechanism,
                text_visual_alignment=hook_res.text_visual_alignment,
                heuristic_score=hook_res.heuristic_score,
                qualitative_strengths=hook_res.qualitative_strengths,
                qualitative_weaknesses=hook_res.qualitative_weaknesses,
                recommendations=hook_res.recommendations,
                model_name=hook_res.model_name,
            )
            session.add(hook_db)

            # Copy analysis
            copy_db = ContentCopyAnalysis(
                job_id=job.id,
                item_uuid=item.uuid,
                original_caption=copy_res.original_caption,
                opening_sentence=copy_res.opening_sentence,
                primary_message=copy_res.primary_message,
                main_topic=copy_res.main_topic,
                secondary_topics=copy_res.secondary_topics,
                tone_of_voice=copy_res.tone_of_voice,
                writing_style=copy_res.writing_style,
                emotional_framing=copy_res.emotional_framing,
                persuasion_techniques=copy_res.persuasion_techniques,
                content_objective=copy_res.content_objective,
                audience_address=copy_res.audience_address,
                hashtag_strategy=copy_res.hashtag_strategy,
                cta_type=copy_res.cta_type,
                cta_text=copy_res.cta_text,
                is_explicit_cta=copy_res.is_explicit_cta,
                caption_structure=copy_res.caption_structure,
                sentence_characteristics=copy_res.sentence_characteristics,
                readability_observations=copy_res.readability_observations,
                brand_voice_indicators=copy_res.brand_voice_indicators,
                summary=copy_res.summary,
            )
            session.add(copy_db)

            # Narrative analysis
            narrative_db = ContentNarrativeAnalysis(
                job_id=job.id,
                item_uuid=item.uuid,
                narrative_pattern=story_res.narrative_pattern,
                summary=story_res.summary,
                stages=[asdict(s) for s in story_res.stages],
            )
            session.add(narrative_db)

            # Video deconstruction
            if video_decomp_res and video_decomp_res.scenes:
                video_db = ContentVideoAnalysis(
                    job_id=job.id,
                    item_uuid=item.uuid,
                    duration=video_decomp_res.duration,
                    aspect_ratio=video_decomp_res.aspect_ratio,
                    width=video_decomp_res.width,
                    height=video_decomp_res.height,
                    scene_count=video_decomp_res.scene_count,
                    avg_scene_duration=video_decomp_res.avg_scene_duration,
                    editing_pace=video_decomp_res.editing_pace,
                    opening_style=video_decomp_res.opening_style,
                    visual_style=video_decomp_res.visual_style,
                    has_talking_head=video_decomp_res.has_talking_head,
                    has_broll=video_decomp_res.has_broll,
                    has_graphics=video_decomp_res.has_graphics,
                    has_subtitles=video_decomp_res.has_subtitles,
                    ending_style=video_decomp_res.ending_style,
                    production_characteristics=video_decomp_res.production_characteristics,
                )
                session.add(video_db)
                session.flush()
                for sc in video_decomp_res.scenes:
                    scene_db = ContentVideoScene(
                        video_analysis_id=video_db.id,
                        scene_index=sc.scene_index,
                        start_time=sc.start_time,
                        end_time=sc.end_time,
                        duration=sc.duration,
                        visual_description=sc.visual_description,
                        camera_framing=sc.camera_framing,
                        camera_movement=sc.camera_movement,
                        visible_text=sc.visible_text,
                        editing_notes=sc.editing_notes,
                        scene_classification=sc.scene_classification,
                        confidence=sc.confidence,
                    )
                    session.add(scene_db)

            # Final status determination
            if media_available:
                job.status = "COMPLETED"
            else:
                job.status = "PARTIAL"
                job.error_category = "MEDIA_UNAVAILABLE"
                job.error_message = "Video media was inaccessible or expired; text and caption analysis completed."

            job.stage = "COMPLETED"
            job.progress_percent = 100.0
            job.completed_at = utc_now()
            session.flush()

            # Refresh creator DNA if author username is known
            if author_info.get("username"):
                try:
                    aggregate_creator_dna(
                        session=session,
                        platform=item.platform,
                        username=author_info["username"],
                    )
                except Exception as exc:
                    logger.warning("Failed to refresh creator DNA for %s: %s", author_info.get("username"), exc)

        # Cleanup temporary files outside DB session
        cleanup_temp_file(temp_audio_path)
        cleanup_temp_file(temp_video_path)
        logger.info("Finished analysis job %s", job_id_str)


# Global singleton worker instance
social_intelligence_worker = SocialIntelligenceWorker()
