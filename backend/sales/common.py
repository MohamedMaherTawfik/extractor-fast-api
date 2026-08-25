"""Shared deterministic helpers for sales services."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4


CENT = Decimal("0.01")
FOUR_DP = Decimal("0.0001")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def quantity(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value)).quantize(FOUR_DP, rounding=ROUND_HALF_UP)


def json_safe(value):
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Enum): return value.value
    if isinstance(value, dict): return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [json_safe(item) for item in value]
    return value


def stable_hash(payload) -> str:
    encoded = json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def model_dict(item, *, exclude: set[str] | None = None) -> dict:
    excluded = exclude or set()
    return {attribute.key: json_safe(getattr(item, attribute.key)) for attribute in item.__mapper__.column_attrs if attribute.key not in excluded}
