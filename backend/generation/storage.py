"""Content-addressed, version-preserving storage for provider outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from backend.core.enums import GeneratedAssetStatus
from backend.core.exceptions import InvalidGeneratedAssetError
from backend.core.paths import paths
from backend.repositories.generation_repository import GenerationRepository
from backend.services.generation_config import load_generation_config


class AssetStorageService:
    def __init__(self, repository: GenerationRepository) -> None:
        self.repository = repository
        self.config = load_generation_config()
        paths.ensure_runtime_directories()

    def store_new(self, job, *, content: bytes, mime_type: str, extension: str | None, metadata: dict,
                  provider: str, model_id: str, model_version: str, prompt_hash: str,
                  seed: int | None, provenance: dict, asset_type: str):
        content = self._validate_content(content, mime_type, extension)
        asset_uid = f"ASSET_{uuid4().hex}"
        asset = self.repository.create_asset(
            job, asset_uid=asset_uid, modality=job.modality, asset_type=asset_type,
            status=GeneratedAssetStatus.DRAFT, current_version=1,
        )
        return asset, self._store_version(
            asset, version=1, content=content, mime_type=mime_type, extension=extension,
            metadata=metadata, provider=provider, model_id=model_id, model_version=model_version,
            prompt_hash=prompt_hash, seed=seed, provenance=provenance,
            parent_asset_version_id=None, change_reason="initial generation", repair_type=None,
        )

    def add_version(self, asset, *, content: bytes, mime_type: str, extension: str | None,
                    metadata: dict, provider: str, model_id: str, model_version: str,
                    prompt_hash: str, seed: int | None, provenance: dict,
                    change_reason: str, repair_type: str | None = None):
        prior = next(item for item in asset.versions if item.version == asset.current_version)
        return self._store_version(
            asset, version=asset.current_version + 1, content=self._validate_content(content, mime_type, extension),
            mime_type=mime_type, extension=extension, metadata=metadata, provider=provider,
            model_id=model_id, model_version=model_version, prompt_hash=prompt_hash, seed=seed,
            provenance=provenance, parent_asset_version_id=prior.id,
            change_reason=change_reason, repair_type=repair_type,
        )

    def store_text(self, job, *, payload: dict, provider: str, model_id: str, model_version: str,
                   prompt_hash: str, seed: int | None, provenance: dict, asset_type: str):
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        return self.store_new(
            job, content=content, mime_type="application/json", extension="json", metadata=payload,
            provider=provider, model_id=model_id, model_version=model_version,
            prompt_hash=prompt_hash, seed=seed, provenance=provenance, asset_type=asset_type,
        )

    def store_raw_response(self, job_uid: str, payload: dict) -> str:
        safe = self._redact(payload)
        target = paths.resolve_under(paths.provider_responses, f"{paths.safe_component(job_uid)}.json")
        target.write_text(json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
        return paths.relative(target).as_posix()

    def archive(self, asset, *, reason: str):
        asset.status = GeneratedAssetStatus.ARCHIVED
        asset.archived_at = datetime.now(UTC)
        asset.archive_reason = reason

    def validate_reference_path(self, relative_path: str, mime_type: str, checksum: str | None = None) -> Path:
        try:
            source = paths.resolve_under(paths.reference_assets, relative_path)
        except ValueError as exc:
            raise InvalidGeneratedAssetError("Reference path traversal is not allowed") from exc
        if mime_type not in self.config.allowed_mime_types:
            raise InvalidGeneratedAssetError("Unsupported reference MIME type")
        expected_extension = self.config.allowed_mime_types[mime_type]
        if source.suffix.lower().lstrip(".") not in {expected_extension, "jpeg" if expected_extension == "jpg" else expected_extension}:
            raise InvalidGeneratedAssetError("Reference extension and MIME type disagree")
        if not source.is_file() or source.stat().st_size > self.config.max_asset_size_bytes:
            raise InvalidGeneratedAssetError("Reference is missing or exceeds configured size")
        actual = sha256(source.read_bytes()).hexdigest()
        if checksum and checksum != actual:
            raise InvalidGeneratedAssetError("Reference checksum mismatch")
        return source

    def _store_version(self, asset, *, version, content, mime_type, extension, metadata, provider,
                       model_id, model_version, prompt_hash, seed, provenance,
                       parent_asset_version_id, change_reason, repair_type):
        checksum = sha256(content).hexdigest()
        ext = self.config.allowed_mime_types[mime_type]
        directory = paths.resolve_under(paths.generated_assets, f"{paths.safe_component(asset.modality)}/{asset.asset_uid}")
        directory.mkdir(parents=True, exist_ok=True)
        target = paths.resolve_under(directory, f"v{version}_{checksum[:12]}.{ext}")
        target.write_bytes(content)
        relative = paths.relative(target).as_posix()
        return self.repository.add_asset_version(
            asset, version=version, parent_asset_version_id=parent_asset_version_id,
            relative_path=relative, checksum=checksum, mime_type=mime_type, file_size=len(content),
            width=metadata.get("width"), height=metadata.get("height"),
            duration_seconds=metadata.get("duration_seconds"), aspect_ratio=metadata.get("aspect_ratio"),
            format=ext, color_profile=metadata.get("color_profile"), provider=provider,
            model_id=model_id, model_version=model_version, prompt_hash=prompt_hash, seed=seed,
            metadata_payload=metadata, provenance=provenance, qa_status="pending",
            change_reason=change_reason, repair_type=repair_type,
        )

    def _validate_content(self, content, mime_type, extension):
        if not isinstance(content, bytes) or not content:
            raise InvalidGeneratedAssetError("Provider output must contain non-empty bytes")
        if len(content) > self.config.max_asset_size_bytes:
            raise InvalidGeneratedAssetError("Provider output exceeds configured size")
        expected = self.config.allowed_mime_types.get(mime_type)
        if expected is None:
            raise InvalidGeneratedAssetError(f"Unsupported MIME type: {mime_type}")
        if extension and extension.lower().lstrip(".") not in {expected, "jpeg" if expected == "jpg" else expected}:
            raise InvalidGeneratedAssetError("Provider extension and MIME type disagree")
        return content

    @classmethod
    def _redact(cls, value):
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if any(token in key.lower() for token in ("key", "secret", "token", "password")) else cls._redact(item)) for key, item in value.items()}
        if isinstance(value, list): return [cls._redact(item) for item in value]
        if isinstance(value, bytes): return f"<bytes:{len(value)}>"
        return value
