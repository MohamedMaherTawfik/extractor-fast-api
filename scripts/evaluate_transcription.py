"""Evaluate selected faster-whisper models on one explicitly supplied audio file."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path

from faster_whisper import WhisperModel


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    ref, hyp = _words(reference), _words(hypothesis)
    if not ref:
        return None
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i]
        for j, hyp_word in enumerate(hyp, start=1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ref_word != hyp_word)))
        previous = current
    return round(previous[-1] / len(ref), 4)


def evaluate(audio: Path, model_name: str, reference: str | None, entities: list[str], device: str, compute_type: str) -> dict:
    started = time.perf_counter()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    loaded = time.perf_counter()
    segments_gen, info = model.transcribe(
        str(audio), language="ar", beam_size=5, vad_filter=True,
        word_timestamps=True, condition_on_previous_text=False,
    )
    segments = []
    for segment in segments_gen:
        text = segment.text.strip()
        if text:
            segments.append({
                "start": round(segment.start, 2), "end": round(segment.end, 2), "text": text,
                "confidence": round(math.exp(max(segment.avg_logprob, -10.0)), 3),
            })
    transcript = " ".join(segment["text"] for segment in segments)
    normalized_segments = [" ".join(_words(segment["text"])) for segment in segments]
    normalized_transcript = " ".join(_words(transcript))
    found_entities = [entity for entity in entities if " ".join(_words(entity)) in normalized_transcript]
    return {
        "model": model_name,
        "audio": str(audio),
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "audio_duration_seconds": round(info.duration, 3),
        "model_load_seconds": round(loaded - started, 3),
        "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        "average_segment_confidence": round(sum(s["confidence"] for s in segments) / len(segments), 3) if segments else None,
        "timestamps_monotonic": all(b["start"] >= a["start"] and b["end"] >= b["start"] for a, b in zip(segments, segments[1:])),
        "repeated_phrase_count": len(normalized_segments) - len(set(normalized_segments)),
        "wer": word_error_rate(reference, transcript) if reference else None,
        "reference_available": reference is not None,
        "entity_recall": round(len(found_entities) / len(entities), 3) if entities else None,
        "entities_found": found_entities,
        "transcript": transcript,
        "segments": segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--models", nargs="+", default=["base", "small"])
    parser.add_argument("--reference-file", type=Path)
    parser.add_argument("--entities", nargs="*", default=[])
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reference = args.reference_file.read_text(encoding="utf-8") if args.reference_file else None
    results = [evaluate(args.audio, model, reference, args.entities, args.device, args.compute_type) for model in args.models]
    rendered = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
