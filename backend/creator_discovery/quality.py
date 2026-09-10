"""Creator profile evidence completeness and analysis-readiness rules."""

from __future__ import annotations

from typing import Any, Iterable


EVIDENCE_WEIGHTS = {
    "profile_url": 10,
    "username": 10,
    "display_name": 15,
    "bio": 15,
    "followers": 15,
    "following": 10,
    "content_count": 10,
    "verified": 5,
    "content_samples": 10,
}


def data_completeness(value: Any, *, has_content_samples: bool = False) -> float:
    fields = {
        "profile_url": getattr(value, "profile_url", None),
        "username": getattr(value, "username", None),
        "display_name": getattr(value, "display_name", None),
        "bio": getattr(value, "public_bio", None) or getattr(value, "bio", None),
        "followers": getattr(value, "followers", None),
        "following": getattr(value, "following", None),
        "content_count": getattr(value, "content_count", None),
        "verified": getattr(value, "verified", None),
        "content_samples": has_content_samples,
    }
    def present(field: str, value: Any) -> bool:
        if field == "verified":
            return value is not None
        if field == "content_samples":
            return bool(value)
        if isinstance(value, str):
            return bool(value.strip())
        return value is not None

    score = sum(
        EVIDENCE_WEIGHTS[field]
        for field, value in fields.items()
        if present(field, value)
    )
    return float(min(100, score))


def collection_status(completeness: float) -> str:
    return "DATA_COLLECTED" if completeness >= 70 else "DATA_COLLECTION_REQUIRED"


def analysis_is_ready(accounts: Iterable[Any], samples: Iterable[Any]) -> bool:
    account_rows = list(accounts)
    sample_rows = list(samples)
    sample_has_text = any(
        (getattr(item, "title", None) or getattr(item, "caption", None))
        for item in sample_rows
    )
    if sample_rows and sample_has_text:
        return True
    for account in account_rows:
        bio = (getattr(account, "bio", None) or "").strip()
        if len(bio) >= 40 and data_completeness(account) >= 60:
            return True
    return False


def aggregate_connector_requirement(accounts: Iterable[Any]) -> str:
    requirements = {
        str(getattr(item, "connector_requirement", "") or "")
        for item in accounts
    }
    for value in (
        "TOKEN_EXPIRED", "TOKEN_INVALID", "PERMISSION_MISSING", "ACCOUNT_NOT_LINKED",
        "ACCOUNT_NOT_ACCESSIBLE", "RATE_LIMITED", "API_UNAVAILABLE", "API_REQUIRED",
        "API_ERROR", "NOT_CONFIGURED", "MANUAL_URL_REQUIRED",
    ):
        if value in requirements:
            return value
    return "NONE"
