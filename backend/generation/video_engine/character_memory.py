"""Durable character identity memory backed by project-relative files."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.core.exceptions import ConflictError, NotFoundError, ReferenceSafetyError
from backend.core.paths import paths
from backend.generation.video_engine.schemas import CharacterProfile


ALLOWED_REFERENCE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class CharacterMemory:
    def __init__(self, root: Path | None = None, *, max_size_bytes: int = 25 * 1024 * 1024) -> None:
        self.root = (root or (paths.reference_assets / "video_characters")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_bytes
        self._lock = RLock()

    def create(
        self, *, name: str, image: bytes, mime_type: str,
        identity_data: dict[str, Any] | None = None,
        style_profile: dict[str, Any] | None = None,
        recurring_attributes: list[str] | None = None,
        negative_constraints: list[str] | None = None,
        character_id: str | None = None,
    ) -> CharacterProfile:
        if mime_type not in ALLOWED_REFERENCE_TYPES:
            raise ReferenceSafetyError("Character reference must be a JPEG, PNG, or WebP image")
        if not image or len(image) > self.max_size_bytes:
            raise ReferenceSafetyError("Character reference is empty or exceeds the configured size limit")
        safe_name = name.strip()
        if not safe_name:
            raise ReferenceSafetyError("Character name is required")
        identifier = character_id or f"CHAR_{uuid4().hex}"
        identifier = paths.safe_component(identifier)
        directory = self.root / identifier
        with self._lock:
            if directory.exists():
                raise ConflictError(f"Character {identifier} already exists")
            directory.mkdir(parents=True)
            reference = directory / f"reference_v001{ALLOWED_REFERENCE_TYPES[mime_type]}"
            reference.write_bytes(image)
            now = datetime.now(UTC)
            profile = CharacterProfile(
                character_id=identifier, name=safe_name, version=1,
                reference_image=paths.relative(reference).as_posix(),
                reference_checksum=sha256(image).hexdigest(),
                identity_data=identity_data or {}, style_profile=style_profile or {},
                recurring_attributes=recurring_attributes or [],
                negative_constraints=negative_constraints or [],
                created_at=now, updated_at=now,
            )
            self._write(directory / "profile.json", profile.model_dump(mode="json"))
            return profile

    def get(self, character_id: str) -> CharacterProfile:
        source = self.root / paths.safe_component(character_id) / "profile.json"
        if not source.exists():
            raise NotFoundError(f"Character {character_id} was not found")
        return CharacterProfile.model_validate_json(source.read_text(encoding="utf-8"))

    def list(self) -> list[CharacterProfile]:
        profiles = []
        for source in self.root.glob("*/profile.json"):
            try:
                profiles.append(CharacterProfile.model_validate_json(source.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(profiles, key=lambda item: item.updated_at, reverse=True)

    def reference_path(self, profile: CharacterProfile) -> Path:
        target = paths.resolve_under(paths.project_root, profile.reference_image)
        if not target.exists():
            raise NotFoundError(f"Reference image for {profile.character_id} is missing")
        return target

    @staticmethod
    def _write(target: Path, payload: dict[str, Any]) -> None:
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
