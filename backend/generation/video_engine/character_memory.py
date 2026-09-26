"""Durable character identity memory backed by project-relative files."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from struct import unpack
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.core.exceptions import ConflictError, NotFoundError, ReferenceSafetyError
from backend.core.paths import paths
from backend.generation.video_engine.schemas import CharacterProfile


ALLOWED_REFERENCE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class CharacterMemory:
    def __init__(
        self, root: Path | None = None, *, max_size_bytes: int = 25 * 1024 * 1024,
        max_dimension: int = 12000,
    ) -> None:
        self.root = (root or (paths.reference_assets / "video_characters")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_bytes
        self.max_dimension = max_dimension
        self._lock = RLock()

    def create(
        self, *, name: str, image: bytes, mime_type: str, filename: str | None = None,
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
        detected_mime, extension, width, height = _inspect_image(image)
        if detected_mime != mime_type:
            raise ReferenceSafetyError("Character reference MIME type does not match image content")
        if filename:
            if Path(filename).name != filename:
                raise ReferenceSafetyError("Character reference filename is invalid")
            allowed_extensions = {extension, ".jpeg" if extension == ".jpg" else extension}
            if Path(filename).suffix.lower() not in allowed_extensions:
                raise ReferenceSafetyError("Character reference extension does not match image content")
        if width < 32 or height < 32 or width > self.max_dimension or height > self.max_dimension:
            raise ReferenceSafetyError("Character reference dimensions are outside the configured limits")
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
            if size < 2 or index + size > len(content):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and index + 7 < len(content):
                height, width = unpack(">HH", content[index + 3:index + 7])
                return "image/jpeg", ".jpg", width, height
            index += size
    if content.startswith(b"RIFF") and len(content) >= 30 and content[8:12] == b"WEBP":
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
    raise ReferenceSafetyError("Character reference content is not a valid PNG, JPEG, or WebP image")
