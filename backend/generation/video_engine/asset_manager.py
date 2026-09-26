"""Versioned file persistence for video jobs and EMY assets."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.core.exceptions import InvalidGeneratedAssetError, NotFoundError
from backend.core.paths import paths
from backend.generation.video_engine.schemas import BatchRecord, VideoGenerationRequest, VideoJob


VIDEO_MIME_TYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".gif": "image/gif"}


class VideoAssetManager:
    def __init__(self, state_root: Path | None = None, asset_root: Path | None = None) -> None:
        self.state_root = (state_root or (paths.data / "video_generation")).resolve()
        self.asset_root = (asset_root or (paths.generated_assets / "video_studio")).resolve()
        self.jobs_root = self.state_root / "jobs"
        self.batches_root = self.state_root / "batches"
        self.assets_root = self.asset_root
        for directory in (self.jobs_root, self.batches_root, self.assets_root):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create_job(self, request: VideoGenerationRequest, *, batch_id: str | None = None) -> VideoJob:
        now = datetime.now(UTC)
        job = VideoJob(
            job_id=f"VJOB_{uuid4().hex}", batch_id=batch_id, status="QUEUED", progress=0,
            stage="Queued for GPU worker", request=request.model_dump(mode="json"),
            created_at=now, updated_at=now,
        )
        self.save_job(job)
        return job

    def save_job(self, job: VideoJob) -> VideoJob:
        job.updated_at = datetime.now(UTC)
        with self._lock:
            self._write(self.jobs_root / f"{paths.safe_component(job.job_id)}.json", job.model_dump(mode="json"))
        return job

    def get_job(self, job_id: str) -> VideoJob:
        source = self.jobs_root / f"{paths.safe_component(job_id)}.json"
        if not source.exists():
            raise NotFoundError(f"Video job {job_id} was not found")
        return VideoJob.model_validate_json(source.read_text(encoding="utf-8"))

    def list_jobs(self, *, limit: int = 100, batch_id: str | None = None) -> list[VideoJob]:
        jobs = []
        for source in self.jobs_root.glob("VJOB_*.json"):
            try:
                job = VideoJob.model_validate_json(source.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if batch_id is None or job.batch_id == batch_id:
                jobs.append(job)
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)[:limit]

    def create_batch(self, job_ids: list[str]) -> BatchRecord:
        record = BatchRecord(
            batch_id=f"VBATCH_{uuid4().hex}", status="QUEUED", job_ids=job_ids,
            total=len(job_ids), created_at=datetime.now(UTC),
        )
        self.save_batch(record)
        return record

    def save_batch(self, record: BatchRecord) -> None:
        with self._lock:
            self._write(self.batches_root / f"{paths.safe_component(record.batch_id)}.json", record.model_dump(mode="json"))

    def get_batch(self, batch_id: str) -> BatchRecord:
        source = self.batches_root / f"{paths.safe_component(batch_id)}.json"
        if not source.exists():
            raise NotFoundError(f"Video batch {batch_id} was not found")
        return BatchRecord.model_validate_json(source.read_text(encoding="utf-8"))

    def list_batches(self, limit: int = 100) -> list[BatchRecord]:
        records = []
        for source in self.batches_root.glob("VBATCH_*.json"):
            try:
                records.append(BatchRecord.model_validate_json(source.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda item: item.created_at, reverse=True)[:limit]

    def save_video(
        self, *, job: VideoJob, content: bytes, source_filename: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        suffix = Path(source_filename).suffix.lower()
        if suffix not in VIDEO_MIME_TYPES:
            raise InvalidGeneratedAssetError(f"Unsupported ComfyUI video output: {suffix or 'no extension'}")
        if not content:
            raise InvalidGeneratedAssetError("ComfyUI returned an empty video")
        if not _valid_video_content(content, suffix):
            raise InvalidGeneratedAssetError("ComfyUI output content does not match its declared video extension")
        asset_id = str((job.final_video or {}).get("asset_id") or f"VAST_{uuid4().hex}")
        directory = self.assets_root / paths.safe_component(asset_id)
        directory.mkdir(parents=True, exist_ok=True)
        existing = sorted(directory.glob("v*_metadata.json"))
        version = len(existing) + 1
        filename = f"v{version:03d}{suffix}"
        target = directory / filename
        target.write_bytes(content)
        checksum = sha256(content).hexdigest()
        record = {
            "asset_id": asset_id, "version": version,
            "relative_path": paths.relative(target).as_posix(),
            "filename": filename, "mime_type": VIDEO_MIME_TYPES[suffix],
            "file_size": len(content), "checksum": checksum,
            "job_id": job.job_id, "saved": False,
            "metadata": metadata, "created_at": datetime.now(UTC).isoformat(),
            "preview_url": f"/video-studio/assets/{asset_id}/content?version={version}",
        }
        self._write(directory / f"v{version:03d}_metadata.json", record)
        self._write(directory / "asset.json", record)
        return record

    def get_asset(self, asset_id: str, version: int | None = None) -> dict[str, Any]:
        directory = self.assets_root / paths.safe_component(asset_id)
        source = directory / (f"v{version:03d}_metadata.json" if version else "asset.json")
        if not source.exists():
            raise NotFoundError(f"Video asset {asset_id} was not found")
        return json.loads(source.read_text(encoding="utf-8"))

    def list_assets(self, limit: int = 100) -> list[dict[str, Any]]:
        records = []
        for source in self.assets_root.glob("*/asset.json"):
            try:
                records.append(json.loads(source.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]

    def asset_path(self, asset_id: str, version: int | None = None) -> tuple[Path, dict[str, Any]]:
        record = self.get_asset(asset_id, version)
        target = paths.resolve_under(paths.project_root, record["relative_path"])
        if not target.exists():
            raise NotFoundError(f"Video file for asset {asset_id} is missing")
        return target, record

    def mark_saved(self, asset_id: str) -> dict[str, Any]:
        record = self.get_asset(asset_id)
        record["saved"] = True
        record["saved_at"] = datetime.now(UTC).isoformat()
        directory = self.assets_root / paths.safe_component(asset_id)
        self._write(directory / "asset.json", record)
        version_source = directory / f"v{int(record['version']):03d}_metadata.json"
        self._write(version_source, record)
        job_id = record.get("job_id")
        if job_id:
            job = self.get_job(str(job_id))
            if job.final_video and job.final_video.get("asset_id") == asset_id:
                job.final_video = record
                self.save_job(job)
        return record

    @staticmethod
    def _write(target: Path, payload: dict[str, Any]) -> None:
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def _valid_video_content(content: bytes, suffix: str) -> bool:
    if suffix in {".mp4", ".mov"}:
        return len(content) >= 12 and content[4:8] == b"ftyp"
    if suffix == ".webm":
        return content.startswith(b"\x1a\x45\xdf\xa3")
    if suffix == ".gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    return False
