"""Platform-neutral pagination state and page result."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PaginationState(BaseModel):
    cursor: str | None = None
    page_token: str | None = None
    offset: int | None = Field(default=None, ge=0)
    next_url: str | None = None

    @model_validator(mode="after")
    def one_strategy_per_state(self) -> "PaginationState":
        values = (self.cursor, self.page_token, self.offset, self.next_url)
        if sum(value is not None for value in values) > 1:
            raise ValueError("Pagination state must use one strategy at a time")
        return self

    def fingerprint(self) -> str:
        return self.model_dump_json(exclude_none=True)


@dataclass(frozen=True, slots=True)
class ContentPage:
    items: Sequence[Mapping[str, Any]]
    next_state: PaginationState | None = None
    collection_completed: bool = True
