"""Streaming media fingerprint and version-aware analysis cache keys."""

import hashlib
import json

from backend.core.paths import paths
from backend.db.models.content_item import ContentItem
from backend.schemas.analysis import AnalysisOptions


class AnalysisCacheKeyBuilder:
    def __init__(self, chunk_size: int) -> None:
        self.chunk_size = chunk_size

    def media_hash(self, content: ContentItem) -> str:
        if content.local_media_path:
            candidate = paths.resolve_under(paths.project_root, content.local_media_path)
            if candidate.is_file():
                digest = hashlib.sha256()
                with candidate.open("rb") as media_file:
                    while chunk := media_file.read(self.chunk_size):
                        digest.update(chunk)
                return digest.hexdigest()
        if content.content_hash:
            return content.content_hash
        fallback = {
            "content_uid": content.content_uid,
            "platform": content.platform.value,
            "platform_content_id": content.platform_content_id,
            "updated_at": content.updated_at.isoformat(),
        }
        return _hash_json(fallback)

    def cache_key(
        self,
        *,
        media_hash: str,
        analyzer_version: str,
        rules_version: str,
        taxonomy_version: str,
        model_version: str,
        rule_ids: list[str],
        options: AnalysisOptions,
    ) -> str:
        return _hash_json(
            {
                "media_hash": media_hash,
                "analyzer_version": analyzer_version,
                "rules_version": rules_version,
                "taxonomy_version": taxonomy_version,
                "model_version": model_version,
                "rule_ids": sorted(rule_ids),
                "mode": options.mode.value,
            }
        )


def _hash_json(value: dict) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
