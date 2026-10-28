"""Audio extraction and speech-to-text transcription with faster-whisper and FFmpeg."""

from __future__ import annotations

import logging
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import imageio_ffmpeg

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AudioExtractionResult:
    audio_path: Path | None
    has_audio: bool
    duration_seconds: float | None = None
    error_message: str | None = None


@dataclass(slots=True)
class TranscriptSegmentData:
    segment_index: int
    start_time: float
    end_time: float
    text: str
    speaker: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class TranscriptionResult:
    language: str | None
    language_probability: float | None
    full_text: str
    duration_seconds: float | None
    model_name: str
    status: str  # completed, no_audio, failed
    segments: list[TranscriptSegmentData] = field(default_factory=list)
    error_message: str | None = None


def extract_audio(
    video_path: Path,
    output_wav_path: Path | None = None,
) -> AudioExtractionResult:
    """Extract audio track from video as 16kHz mono WAV using FFmpeg."""
    if not video_path.exists():
        return AudioExtractionResult(
            audio_path=None, has_audio=False, error_message=f"Video file not found: {video_path}"
        )

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if output_wav_path is None:
        output_wav_path = video_path.with_suffix(".wav")

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_wav_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            err = proc.stderr.lower()
            if "does not contain any stream" in err or "output file is empty" in err or "matches no streams" in err:
                return AudioExtractionResult(
                    audio_path=None, has_audio=False, error_message="Video contains no audio track"
                )
            return AudioExtractionResult(
                audio_path=None,
                has_audio=False,
                error_message=f"FFmpeg extraction failed (code {proc.returncode}): {proc.stderr[:200]}",
            )

        if not output_wav_path.exists() or output_wav_path.stat().st_size < 100:
            return AudioExtractionResult(
                audio_path=None, has_audio=False, error_message="Extracted audio file is empty"
            )

        return AudioExtractionResult(audio_path=output_wav_path, has_audio=True)
    except subprocess.TimeoutExpired:
        return AudioExtractionResult(
            audio_path=None, has_audio=False, error_message="FFmpeg audio extraction timed out"
        )
    except Exception as exc:
        return AudioExtractionResult(
            audio_path=None, has_audio=False, error_message=f"Audio extraction error: {exc}"
        )


class TranscriberProtocol(Protocol):
    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        ...


class FasterWhisperTranscriber:
    """Local faster-whisper transcriber supporting Arabic, English, and multilingual content."""

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return TranscriptionResult(
                language=None,
                language_probability=None,
                full_text="",
                duration_seconds=0.0,
                model_name=f"faster-whisper-{self.model_size}",
                status="no_audio",
                error_message="Audio file is missing or empty",
            )

        try:
            model = self._get_model()
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            segments: list[TranscriptSegmentData] = []
            text_parts: list[str] = []

            for idx, seg in enumerate(segments_gen, start=1):
                clean_text = seg.text.strip()
                if not clean_text:
                    continue
                # avg_logprob is typically between -1.0 and 0.0; convert to 0-1 probability
                confidence = round(math.exp(max(seg.avg_logprob, -10.0)), 3)
                segments.append(
                    TranscriptSegmentData(
                        segment_index=idx,
                        start_time=round(seg.start, 2),
                        end_time=round(seg.end, 2),
                        text=clean_text,
                        speaker=None,
                        confidence=min(max(confidence, 0.0), 1.0),
                    )
                )
                text_parts.append(clean_text)

            full_text = " ".join(text_parts)
            duration = round(info.duration, 2) if hasattr(info, "duration") and info.duration else None

            return TranscriptionResult(
                language=info.language,
                language_probability=round(info.language_probability, 3) if hasattr(info, "language_probability") else None,
                full_text=full_text,
                duration_seconds=duration,
                model_name=f"faster-whisper-{self.model_size}",
                status="completed" if full_text else "no_speech_detected",
                segments=segments,
            )
        except Exception as exc:
            logger.error("FasterWhisper transcription failed: %s", exc)
            return TranscriptionResult(
                language=None,
                language_probability=None,
                full_text="",
                duration_seconds=None,
                model_name=f"faster-whisper-{self.model_size}",
                status="failed",
                error_message=f"Transcription failure: {exc}",
            )


class MockTranscriber:
    """Mock transcriber for fast offline testing and environments without model weights."""

    def __init__(self, sample_text: str = "مرحبا بكم في هذا الفيديو التعليمي الشيق", language: str = "ar") -> None:
        self.sample_text = sample_text
        self.language = language

    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        segments = [
            TranscriptSegmentData(
                segment_index=1,
                start_time=0.0,
                end_time=4.5,
                text=self.sample_text,
                confidence=0.98,
                speaker="Speaker 1",
            ),
            TranscriptSegmentData(
                segment_index=2,
                start_time=4.5,
                end_time=9.2,
                text="والسؤال هنا: كيف بدأ كل شيء؟",
                confidence=0.95,
                speaker="Speaker 1",
            ),
        ]
        return TranscriptionResult(
            language=self.language,
            language_probability=0.99,
            full_text=f"{self.sample_text} والسؤال هنا: كيف بدأ كل شيء؟",
            duration_seconds=9.2,
            model_name="mock-transcriber-v1",
            status="completed",
            segments=segments,
        )
