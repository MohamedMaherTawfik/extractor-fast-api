"""Evidence verification for source-derived social intelligence claims."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class VerifiedClaim:
    item_uuid: UUID
    claim_type: str
    claim_text: str
    evidence_type: str
    source_reference: str
    analysis_provider: str
    model_version: str
    verification_status: str
    verification_reason: str
    start_time: float | None = None
    end_time: float | None = None
    evidence_quote: str | None = None
    confidence: float | None = None


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def _transcript_verification(
    quote: str | None,
    start_time: float | None,
    end_time: float | None,
    transcript: Any,
) -> tuple[str, str]:
    if transcript is None or not getattr(transcript, "segments", None):
        return "unsupported", "No original transcript segments are available."
    if not quote:
        return "unsupported", "The claim does not include a transcript quotation."
    if start_time is None or end_time is None or start_time < 0 or end_time < start_time:
        return "invalid", "Transcript timestamps are missing or invalid."
    duration = getattr(transcript, "duration_seconds", None)
    if duration is not None and end_time > duration + 0.25:
        return "invalid", "Evidence timestamp exceeds the transcribed media duration."
    overlapping = [
        segment for segment in transcript.segments
        if segment.end_time >= start_time - 0.25 and segment.start_time <= end_time + 0.25
    ]
    source_text = _normalized(" ".join(segment.text for segment in overlapping))
    if _normalized(quote) not in source_text:
        return "invalid", "Quoted words do not match the transcript at the cited timestamp."
    quality = getattr(transcript, "quality_indicators", None) or {}
    if not quality.get("human_reference_available"):
        average_confidence = quality.get("average_segment_confidence")
        if average_confidence is None or float(average_confidence) < 0.75:
            return "needs_review", "Quote matches raw ASR timestamps, but no human reference exists and ASR confidence is below 0.75."
    return "verified", "Exact transcript words and timestamp range match the original ASR segments."


def _caption_verification(quote: str | None, caption: str | None) -> tuple[str, str]:
    if not caption:
        return "unsupported", "No original caption is available."
    if not quote:
        return "unsupported", "The claim does not include a caption quotation."
    if _normalized(quote) not in _normalized(caption):
        return "invalid", "Quoted words are not present in the original caption."
    return "verified", "Exact text is present in the original caption."


def build_verified_claims(
    *,
    item_uuid: UUID,
    transcript: Any,
    caption: str | None,
    hook_result: Any,
    copy_result: Any,
    narrative_result: Any,
    video_result: Any,
    provider_name: str,
    provider_model: str,
) -> list[VerifiedClaim]:
    """Build and verify the evidence ledger without altering source quotations."""

    claims: list[VerifiedClaim] = []

    spoken = getattr(hook_result, "spoken_hook", None)
    if spoken:
        status, reason = _transcript_verification(
            spoken.exact_text, spoken.start_time, spoken.end_time, transcript
        )
        claims.append(VerifiedClaim(
            item_uuid=item_uuid,
            claim_type="spoken_hook",
            claim_text=f"Opening speech classified as {spoken.key_attention_trigger}",
            evidence_type="transcript",
            source_reference="raw transcript segments",
            start_time=spoken.start_time,
            end_time=spoken.end_time,
            evidence_quote=spoken.exact_text,
            analysis_provider=provider_name,
            model_version=provider_model,
            verification_status=status,
            verification_reason=reason,
            confidence=(getattr(transcript, "quality_indicators", {}) or {}).get("average_segment_confidence") if status == "needs_review" else (0.95 if status == "verified" else 0.0),
        ))

    text_hook = getattr(hook_result, "text_hook", None)
    if text_hook and text_hook.opening_caption_sentence:
        status, reason = _caption_verification(text_hook.opening_caption_sentence, caption)
        claims.append(VerifiedClaim(
            item_uuid=item_uuid,
            claim_type="caption_hook",
            claim_text="Opening caption text used as a hook",
            evidence_type="caption",
            source_reference="original social post caption",
            evidence_quote=text_hook.opening_caption_sentence,
            analysis_provider=provider_name,
            model_version=provider_model,
            verification_status=status,
            verification_reason=reason,
            confidence=0.98 if status == "verified" else 0.0,
        ))

    for citation in getattr(copy_result, "evidence_citations", []) or []:
        quote = citation.get("verbatim_quote") if isinstance(citation, dict) else None
        status, reason = _caption_verification(quote, caption)
        claims.append(VerifiedClaim(
            item_uuid=item_uuid,
            claim_type="copy_analysis",
            claim_text="Copywriting interpretation supported by cited caption text",
            evidence_type="caption",
            source_reference="original social post caption",
            evidence_quote=quote,
            analysis_provider=provider_name,
            model_version=provider_model,
            verification_status=status,
            verification_reason=reason,
            confidence=citation.get("confidence") if isinstance(citation, dict) else None,
        ))

    for stage in getattr(narrative_result, "stages", []) or []:
        if transcript is not None and getattr(transcript, "segments", None):
            status, reason = _transcript_verification(
                stage.evidence, stage.start_time, stage.end_time, transcript
            )
            evidence_type = "transcript"
            source_reference = "raw transcript segments"
        else:
            status, reason = _caption_verification(stage.evidence, caption)
            evidence_type = "caption"
            source_reference = "original social post caption"
        claims.append(VerifiedClaim(
            item_uuid=item_uuid,
            claim_type="narrative_stage",
            claim_text=f"{stage.stage_name}: {stage.description}",
            evidence_type=evidence_type,
            source_reference=source_reference,
            start_time=stage.start_time if evidence_type == "transcript" else None,
            end_time=stage.end_time if evidence_type == "transcript" else None,
            evidence_quote=stage.evidence,
            analysis_provider=provider_name,
            model_version=provider_model,
            verification_status=status,
            verification_reason=reason,
            confidence=(getattr(transcript, "quality_indicators", {}) or {}).get("average_segment_confidence") if status == "needs_review" else stage.confidence,
        ))

    for scene in getattr(video_result, "scenes", []) or []:
        metrics = scene.sampled_metrics or {}
        if not metrics:
            continue
        metric_text = ", ".join(
            f"{key}={value}" for key, value in sorted(metrics.items())
            if key in {"luminance", "contrast", "dominant_color", "color_tone"}
        )
        claims.append(VerifiedClaim(
            item_uuid=item_uuid,
            claim_type="frame_statistics",
            claim_text=scene.visual_description,
            evidence_type="video_frame_statistics",
            source_reference=f"sampled video frame in scene {scene.scene_index}",
            start_time=scene.start_time,
            end_time=scene.end_time,
            evidence_quote=metric_text,
            analysis_provider="PyAV/NumPy",
            model_version="frame-statistics-v1",
            verification_status="verified",
            verification_reason="Claim contains only calculated frame statistics; no semantic object or action inference.",
            confidence=1.0,
        ))

    return claims


def summarize_verification(claims: list[VerifiedClaim]) -> dict[str, Any]:
    counts = {status: sum(1 for claim in claims if claim.verification_status == status) for status in ("verified", "needs_review", "invalid", "unsupported")}
    return {
        "total_claims": len(claims),
        **counts,
        "quality_status": "passed" if counts["needs_review"] == 0 and counts["invalid"] == 0 and counts["unsupported"] == 0 else "needs_review",
    }
