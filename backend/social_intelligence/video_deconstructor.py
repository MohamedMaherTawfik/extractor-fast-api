"""Video deconstruction, frame sampling, scene understanding, and temporal analysis."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import av
import imageio_ffmpeg
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SceneData:
    scene_index: int
    start_time: float
    end_time: float
    duration: float
    visual_description: str
    camera_framing: str | None = None
    camera_movement: str | None = None
    visible_text: str | None = None
    editing_notes: str | None = None
    scene_classification: str | None = None
    confidence: float | None = None
    sampled_metrics: dict[str, Any] | None = None


@dataclass(slots=True)
class VideoDeconstructionResult:
    duration: float | None
    aspect_ratio: str | None
    width: int | None
    height: int | None
    scene_count: int
    avg_scene_duration: float | None
    editing_pace: str
    opening_style: str
    visual_style: str
    has_talking_head: bool
    has_broll: bool
    has_graphics: bool
    has_subtitles: bool
    ending_style: str
    production_characteristics: str
    scenes: list[SceneData] = field(default_factory=list)
    error_message: str | None = None
    shot_distribution: dict[str, Any] | None = None
    audio_visual_alignment: dict[str, Any] | None = None
    visual_analysis_level: str = "sampled_frames"


def get_video_stream_info(video_path: Path) -> dict[str, Any]:
    """Extract video stream dimensions, duration, and frame rate via FFmpeg."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-i", str(video_path), "-hide_banner"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        output = proc.stderr
        info: dict[str, Any] = {"width": None, "height": None, "duration": None, "fps": None}

        res_match = re.search(r",\s*(\d{3,4})x(\d{3,4})", output)
        if res_match:
            info["width"] = int(res_match.group(1))
            info["height"] = int(res_match.group(2))

        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if dur_match:
            hours = int(dur_match.group(1))
            minutes = int(dur_match.group(2))
            seconds = float(dur_match.group(3))
            info["duration"] = round(hours * 3600 + minutes * 60 + seconds, 2)

        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", output)
        if fps_match:
            info["fps"] = float(fps_match.group(1))

        return info
    except Exception as exc:
        logger.warning("Failed to extract video stream info: %s", exc)
        return {"width": None, "height": None, "duration": None, "fps": None}


def calculate_aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    ratio = width / height
    if abs(ratio - (9 / 16)) < 0.08:
        return "9:16 (Vertical)"
    if abs(ratio - (16 / 9)) < 0.08:
        return "16:9 (Landscape)"
    if abs(ratio - 1.0) < 0.05:
        return "1:1 (Square)"
    if abs(ratio - (4 / 5)) < 0.08:
        return "4:5 (Portrait)"
    return f"{width}:{height}"


def detect_scenes_ffmpeg(video_path: Path, min_scene_duration: float = 1.0) -> list[float]:
    """Detect shot/scene change timestamps using FFmpeg scene filter."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-i",
        str(video_path),
        "-filter:v",
        "select='gt(scene,0.3)',metadata=print:file=-",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        timestamps = [0.0]
        for line in proc.stdout.splitlines():
            if "pts_time:" in line:
                val = line.split("pts_time:")[1].strip()
                try:
                    ts = float(val)
                    if ts > timestamps[-1] + min_scene_duration:
                        timestamps.append(round(ts, 2))
                except ValueError:
                    continue
        return timestamps
    except Exception as exc:
        logger.warning("Scene detection via FFmpeg failed: %s", exc)
        return [0.0]


def _sample_frame_at_timestamp(container: av.container.InputContainer, timestamp_sec: float) -> np.ndarray | None:
    """Seek to target timestamp and decode a single RGB frame."""
    try:
        stream = container.streams.video[0]
        target_pts = int(timestamp_sec / float(stream.time_base))
        container.seek(target_pts, stream=stream, backward=True, any_frame=False)
        for frame in container.decode(video=0):
            frame_time = float(frame.pts * stream.time_base) if frame.pts is not None else timestamp_sec
            if frame_time + 0.05 >= timestamp_sec:
                return frame.to_ndarray(format="rgb24")
    except Exception as exc:
        logger.debug("Frame sampling at %s sec failed: %s", timestamp_sec, exc)
    return None


def _analyze_frame_pixels(frame: np.ndarray) -> dict[str, Any]:
    """Calculate frame statistics; candidate flags are not semantic detections."""
    h, w, _ = frame.shape
    gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114])

    luminance = round(float(gray.mean()), 1)
    contrast = round(float(gray.std()), 1)

    # Color palette
    mean_r = float(frame[..., 0].mean())
    mean_g = float(frame[..., 1].mean())
    mean_b = float(frame[..., 2].mean())

    color_tone = "warm" if (mean_r - mean_b) > 15 else ("cool" if (mean_b - mean_r) > 15 else "neutral")
    dominant_hex = f"#{int(mean_r):02x}{int(mean_g):02x}{int(mean_b):02x}"

    # Text / Subtitle band detection in lower third (70% - 95% height)
    lower_band = gray[int(h * 0.70):int(h * 0.95), :]
    lower_edge_energy = float(np.abs(np.diff(lower_band, axis=1)).mean())
    overall_edge_energy = float(np.abs(np.diff(gray, axis=1)).mean())
    has_subtitles = lower_edge_energy > (overall_edge_energy * 1.35) and lower_edge_energy > 8.0

    # Upper third banner / headline check (5% - 25% height)
    upper_band = gray[int(h * 0.05):int(h * 0.25), :]
    upper_edge_energy = float(np.abs(np.diff(upper_band, axis=1)).mean())
    has_top_graphics = upper_edge_energy > (overall_edge_energy * 1.4) and upper_edge_energy > 8.5

    # Center face / skin tone ratio
    center_y1, center_y2 = int(h * 0.15), int(h * 0.75)
    center_x1, center_x2 = int(w * 0.25), int(w * 0.75)
    center_crop = frame[center_y1:center_y2, center_x1:center_x2]

    r = center_crop[..., 0].astype(int)
    g = center_crop[..., 1].astype(int)
    b = center_crop[..., 2].astype(int)

    # Skin tone detection in RGB
    skin_mask = (r > 95) & (g > 40) & (b > 20) & (r > g) & (r > b) & (np.abs(r - g) > 15)
    skin_ratio = round(float(skin_mask.sum() / max(center_crop.shape[0] * center_crop.shape[1], 1)), 3)

    return {
        "luminance": luminance,
        "contrast": contrast,
        "color_tone": color_tone,
        "dominant_color": dominant_hex,
        "subtitle_band_detected": has_subtitles,
        "top_graphics_detected": has_top_graphics,
        "center_skin_tone_ratio": skin_ratio,
        "is_talking_head_candidate": skin_ratio > 0.08,
    }


def deconstruct_video(
    video_path: Path,
    known_duration: float | None = None,
    enable_deep_visual: bool = True,
) -> VideoDeconstructionResult:
    """Analyze video temporal structure, pace, scenes, and verifiable visual features."""
    if not video_path.exists():
        return VideoDeconstructionResult(
            duration=None,
            aspect_ratio=None,
            width=None,
            height=None,
            scene_count=0,
            avg_scene_duration=None,
            editing_pace="Unknown",
            opening_style="Unknown",
            visual_style="Unknown",
            has_talking_head=False,
            has_broll=False,
            has_graphics=False,
            has_subtitles=False,
            ending_style="Unknown",
            production_characteristics="Video file not available for deconstruction",
            error_message="Video file not found",
            visual_analysis_level="technical_metrics_only",
        )

    stream_info = get_video_stream_info(video_path)
    width = stream_info.get("width")
    height = stream_info.get("height")
    duration = stream_info.get("duration") or known_duration
    aspect_ratio = calculate_aspect_ratio(width, height)

    raw_scene_times = detect_scenes_ffmpeg(video_path)
    if duration and (not raw_scene_times or raw_scene_times[-1] < duration - 1.0):
        raw_scene_times.append(duration)

    # Frame sampling with PyAV if enabled
    container: av.container.InputContainer | None = None
    if enable_deep_visual:
        try:
            container = av.open(str(video_path))
        except Exception as exc:
            logger.warning("Could not open video with PyAV: %s. Falling back to technical metrics.", exc)
            container = None

    scenes: list[SceneData] = []

    # Handle single continuous shot
    if len(raw_scene_times) <= 1:
        total_d = duration or 10.0
        sampled_metrics = None
        if container:
            frame = _sample_frame_at_timestamp(container, min(1.0, total_d / 2))
            if frame is not None:
                sampled_metrics = _analyze_frame_pixels(frame)

        scenes.append(
            SceneData(
                scene_index=1,
                start_time=0.0,
                end_time=total_d,
                duration=total_d,
                visual_description=(
                    f"Frame statistics: luminance {sampled_metrics['luminance']}, "
                    f"contrast {sampled_metrics['contrast']}, mean color {sampled_metrics['dominant_color']}."
                    if sampled_metrics else "No frame statistics available."
                ),
                camera_framing=None,
                camera_movement=None,
                visible_text=None,
                editing_notes="Single continuous shot take without cut transitions",
                scene_classification="unclassified_frame_sample",
                confidence=1.0 if sampled_metrics else None,
                sampled_metrics=sampled_metrics,
            )
        )
    else:
        for i in range(len(raw_scene_times) - 1):
            s_time = raw_scene_times[i]
            e_time = raw_scene_times[i + 1]
            s_dur = round(e_time - s_time, 2)
            if s_dur <= 0:
                continue

            mid_t = round(s_time + (s_dur * 0.3), 2)
            sampled_metrics = None
            if container:
                frame = _sample_frame_at_timestamp(container, mid_t)
                if frame is not None:
                    sampled_metrics = _analyze_frame_pixels(frame)

            lum = 120.0
            contrast = 45.0
            color_tone = "neutral"

            if sampled_metrics:
                lum = sampled_metrics.get("luminance", 120.0)
                contrast = sampled_metrics.get("contrast", 45.0)
                color_tone = sampled_metrics.get("color_tone", "neutral")

            desc = (
                f"Frame statistics: luminance {lum:.0f}, contrast {contrast:.0f}, "
                f"mean color tone {color_tone}."
            )

            scenes.append(
                SceneData(
                    scene_index=len(scenes) + 1,
                    start_time=s_time,
                    end_time=e_time,
                    duration=s_dur,
                    visual_description=desc,
                    camera_framing=None,
                    camera_movement=None,
                    visible_text=None,
                    editing_notes=f"Shot duration {s_dur}s; cut transition",
                    scene_classification="unclassified_frame_sample",
                    confidence=1.0 if sampled_metrics else None,
                    sampled_metrics=sampled_metrics,
                )
            )

    if container:
        try:
            container.close()
        except Exception:
            pass

    # Shot distribution calculations
    scene_count = len(scenes)
    total_scene_time = sum(s.duration for s in scenes)
    avg_scene_duration = round(total_scene_time / max(scene_count, 1), 2)

    durations = [s.duration for s in scenes]
    shot_dist = {
        "total_shots": scene_count,
        "cuts_per_minute": round((scene_count / max(total_scene_time, 1.0)) * 60, 1),
        "median_shot_duration": round(float(np.median(durations)), 2) if durations else None,
        "shots_under_2s": sum(1 for d in durations if d < 2.0),
        "shots_2s_to_4s": sum(1 for d in durations if 2.0 <= d <= 4.0),
        "shots_over_4s": sum(1 for d in durations if d > 4.0),
    }

    if avg_scene_duration < 2.5:
        editing_pace = "Fast (<2.5s / shot)"
    elif avg_scene_duration <= 5.0:
        editing_pace = "Moderate (2.5s - 5.0s / shot)"
    else:
        editing_pace = "Deliberate (>5.0s / shot)"

    # No object detector, OCR model, pose model, or VLM is used in this path.
    has_talking = False
    has_broll = False
    has_graphics = False
    has_subtitles = False

    opening_style = "Not semantically classified"
    ending_style = "Not semantically classified"
    visual_style = f"Technical format only ({aspect_ratio or 'unknown aspect ratio'}); {editing_pace}"

    production_chars = (
        f"Format: {aspect_ratio or 'Vertical 9:16'}. {scene_count} shots across {round(duration or total_scene_time, 1)}s "
        f"({shot_dist['cuts_per_minute']} cuts/min). Pacing: {editing_pace}."
    )

    return VideoDeconstructionResult(
        duration=duration or total_scene_time,
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        scene_count=scene_count,
        avg_scene_duration=avg_scene_duration,
        editing_pace=editing_pace,
        opening_style=opening_style,
        visual_style=visual_style,
        has_talking_head=has_talking,
        has_broll=has_broll,
        has_graphics=has_graphics,
        has_subtitles=has_subtitles,
        ending_style=ending_style,
        production_characteristics=production_chars,
        scenes=scenes,
        shot_distribution=shot_dist,
        audio_visual_alignment=None,
        visual_analysis_level="frame_statistics_and_scene_detection" if container else "technical_metrics_only",
    )
