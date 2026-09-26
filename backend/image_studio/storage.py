"""Secure local persistence for image-studio references, jobs, and outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from struct import unpack
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.core.exceptions import NotFoundError, ReferenceSafetyError
from backend.core.paths import paths
from backend.image_studio.schemas import ImageReference, ImageStudioJob, ImageStudioSettings


IMAGE_TYPES = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
}


class ImageStudioStorage:
    def __init__(self, state_root: Path | None = None, asset_root: Path | None = None, reference_root: Path | None = None) -> None:
        self.state_root = (state_root or (paths.data / "image_studio")).resolve()
        self.asset_root = (asset_root or (paths.generated_assets / "image_studio")).resolve()
        self.reference_root = (reference_root or (paths.reference_assets / "image_studio")).resolve()
        self.jobs_root = self.state_root / "jobs"
        for directory in (self.jobs_root, self.asset_root, self.reference_root):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def inspect_upload(self, *, filename: str | None, content_type: str | None, content: bytes, max_size: int, max_dimension: int) -> tuple[str, str, int, int]:
        name = filename or ""
        if not name or Path(name).name != name:
            raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: filename is invalid")
        if not content or len(content) > max_size:
            raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: image is empty or exceeds the configured size limit")
        mime_type, extension, width, height = _inspect_image(content)
        if Path(name).suffix.lower() not in {extension, ".jpeg" if extension == ".jpg" else extension}:
            raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: file extension does not match image content")
        supplied = (content_type or "").lower().split(";", 1)[0]
        if supplied and supplied != "application/octet-stream" and supplied != mime_type:
            raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: MIME type does not match image content")
        if width < 32 or height < 32 or width > max_dimension or height > max_dimension:
            raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: image dimensions are outside the configured limits")
        return mime_type, extension, width, height

    def new_job_id(self) -> str:
        return f"IJOB_{uuid4().hex}"

    def create_job(self, *, settings: ImageStudioSettings, prompt: str, negative_prompt: str, character_image: ImageReference, product_image: ImageReference, job_id: str | None = None, execute: bool = True) -> ImageStudioJob:
        now = datetime.now(UTC)
        job = ImageStudioJob(
            job_id=job_id or self.new_job_id(), status="QUEUED", progress=0, stage="Queued for image generation",
            settings=settings.model_dump(mode="json"), character_image=character_image, product_image=product_image,
            prompt=prompt, negative_prompt=negative_prompt, seed=settings.seed, execute=execute, created_at=now, updated_at=now,
        )
        self.save_job(job)
        return job

    def save_reference(self, *, job_id: str, kind: str, original_filename: str, content: bytes, mime_type: str, width: int, height: int) -> ImageReference:
        extension = IMAGE_TYPES[mime_type]
        filename = f"{kind}_{uuid4().hex}{extension}"
        target = self.reference_root / paths.safe_component(job_id) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return ImageReference(filename=filename, mime_type=mime_type, file_size=len(content), width=width, height=height, relative_path=paths.relative(target).as_posix(), checksum=sha256(content).hexdigest())

    def save_job(self, job: ImageStudioJob) -> ImageStudioJob:
        job.updated_at = datetime.now(UTC)
        with self._lock:
            self._write(self.jobs_root / f"{paths.safe_component(job.job_id)}.json", job.model_dump(mode="json"))
        return job

    def get_job(self, job_id: str) -> ImageStudioJob:
        source = self.jobs_root / f"{paths.safe_component(job_id)}.json"
        if not source.exists():
            raise NotFoundError(f"Image Studio job {job_id} was not found")
        return ImageStudioJob.model_validate_json(source.read_text(encoding="utf-8"))

    def list_jobs(self, limit: int = 100) -> list[ImageStudioJob]:
        records = []
        for source in self.jobs_root.glob("IJOB_*.json"):
            try:
                records.append(ImageStudioJob.model_validate_json(source.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda item: item.created_at, reverse=True)[:limit]

    def reference_path(self, reference: ImageReference) -> Path:
        target = paths.resolve_under(paths.project_root, reference.relative_path)
        if not target.exists():
            raise NotFoundError("Image Studio reference file is missing")
        return target

    def save_output(self, *, job: ImageStudioJob, content: bytes, filename: str, metadata: dict[str, Any]) -> dict[str, Any]:
        mime_type, extension, width, height = _inspect_image(content)
        asset_id = f"IAST_{uuid4().hex}"
        directory = self.asset_root / paths.safe_component(asset_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"v001{extension}"
        target.write_bytes(content)
        record = {
            "asset_id": asset_id, "version": 1, "filename": target.name, "mime_type": mime_type,
            "file_size": len(content), "width": width, "height": height, "checksum": sha256(content).hexdigest(),
            "relative_path": paths.relative(target).as_posix(), "job_id": job.job_id, "created_at": datetime.now(UTC).isoformat(),
            "metadata": metadata, "preview_url": f"/image-studio/assets/{asset_id}/content",
        }
        self._write(directory / "asset.json", record)
        return record

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        source = self.asset_root / paths.safe_component(asset_id) / "asset.json"
        if not source.exists():
            raise NotFoundError(f"Image Studio asset {asset_id} was not found")
        return json.loads(source.read_text(encoding="utf-8"))

    def asset_path(self, asset_id: str) -> tuple[Path, dict[str, Any]]:
        record = self.get_asset(asset_id)
        target = paths.resolve_under(paths.project_root, str(record["relative_path"]))
        if not target.exists():
            raise NotFoundError(f"Image Studio asset file for {asset_id} is missing")
        return target, record

    def delete_asset(self, asset_id: str) -> None:
        directory = self.asset_root / paths.safe_component(asset_id)
        record = self.get_asset(asset_id)
        target = paths.resolve_under(paths.project_root, str(record["relative_path"]))
        if target.exists():
            target.unlink()
        metadata = directory / "asset.json"
        if metadata.exists():
            metadata.unlink()
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()
        for job in self.list_jobs(limit=10000):
            updated = [item for item in job.output_images if item.get("asset_id") != asset_id]
            if len(updated) != len(job.output_images):
                job.output_images = updated
                self.save_job(job)

    @staticmethod
    def _write(target: Path, payload: dict[str, Any]) -> None:
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def _inspect_image(content: bytes) -> tuple[str, str, int, int]:
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        width, height = unpack(">II", content[16:24])
        return "image/png", ".png", width, height
    if content.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(content):
                break
            size = unpack(">H", content[index:index + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and index + 7 < len(content):
                height, width = unpack(">HH", content[index + 3:index + 7])
                return "image/jpeg", ".jpg", width, height
            index += size
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP" and len(content) >= 30:
        kind = content[12:16]
        if kind == b"VP8X":
            width = 1 + int.from_bytes(content[24:27], "little")
            height = 1 + int.from_bytes(content[27:30], "little")
            return "image/webp", ".webp", width, height
        if kind == b"VP8L":
            bits = int.from_bytes(content[21:25], "little")
            return "image/webp", ".webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8 ":
            width, height = unpack("<HH", content[26:30])
            return "image/webp", ".webp", width & 0x3FFF, height & 0x3FFF
    raise ReferenceSafetyError("REFERENCE_UPLOAD_FAILED: only valid PNG, JPEG, and WebP images are accepted")
