"""Replaceable platform connector contract."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from backend.connectors.pagination import ContentPage, PaginationState
from backend.schemas.content import NormalizedContent


Payload = Mapping[str, Any]


class BaseConnector(ABC):
    """Contract implemented by every future platform connector."""

    @abstractmethod
    def resolve_account(
        self,
        identifier: str,
        *,
        timeout: float | None = None,
    ) -> Payload:
        """Resolve a user-facing identifier into a platform account."""

    @abstractmethod
    def fetch_profile(
        self,
        account: Payload,
        *,
        timeout: float | None = None,
    ) -> Payload:
        """Fetch raw profile data for a resolved account."""

    @abstractmethod
    def fetch_content_list(
        self,
        account: Payload,
        *,
        pagination: PaginationState | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> ContentPage:
        """Fetch one page of raw content references."""

    @abstractmethod
    def fetch_content_item(
        self,
        content_id: str,
        *,
        timeout: float | None = None,
    ) -> Payload:
        """Fetch a single raw content item."""

    @abstractmethod
    def normalize(self, raw_content: Payload) -> NormalizedContent:
        """Convert platform data into the future canonical content shape."""
