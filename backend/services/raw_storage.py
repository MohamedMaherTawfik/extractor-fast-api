"""Local raw response preservation with recursive secret redaction."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.connectors.config import is_sensitive_key
from backend.core.enums import Platform
from backend.core.paths import paths


class RawContentStore:
    def store(
        self,
        *,
        platform: Platform,
        creator_uid: str,
        raw_content: Mapping[str, Any],
    ) -> str:
        directory = paths.resolve_under(
            paths.raw,
            Path(paths.safe_component(platform.value))
            / paths.safe_component(creator_uid),
        )
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"RAW_{uuid4().hex.upper()}.json"
        target.write_text(
            json.dumps(
                redact_sensitive(raw_content),
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return paths.relative(target).as_posix()

    def rehome(self, stored_path: str, *, creator_uid: str) -> str:
        source = paths.resolve_under(paths.project_root, stored_path)
        if not source.is_relative_to(paths.raw.resolve()) or not source.is_file():
            raise ValueError("Raw response is outside managed raw storage")
        destination = paths.resolve_under(
            paths.raw,
            Path(source.parent.parent.name)
            / paths.safe_component(creator_uid)
            / source.name,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        return paths.relative(destination).as_posix()


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if is_sensitive_key(key)
                else redact_sensitive(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(child) for child in value]
    return value
