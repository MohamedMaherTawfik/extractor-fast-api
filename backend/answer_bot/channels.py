"""Messaging channel adapter contracts, registry, mock channel, and webhook security."""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.answer_bot.config import get_answer_bot_config
from backend.core.exceptions import MessagingProviderError, MessagingValidationError


class BaseMessagingChannel(ABC):
    code: str

    @abstractmethod
    def receive_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def parse_message(self, event: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def send_message(self, message: dict[str, Any]) -> dict[str, Any]: ...

    def send_media(self, message: dict[str, Any]) -> dict[str, Any]: return self.send_message(message)
    def mark_read(self, external_message_id: str) -> bool: return True
    def get_delivery_status(self, external_message_id: str) -> str: return "UNKNOWN"
    def get_message_status(self, external_message_id: str) -> str: return self.get_delivery_status(external_message_id)
    def normalize_contact(self, value: str) -> str: return value.strip().casefold()
    def normalize_thread(self, value: str) -> str: return value.strip()


class MockChannelAdapter(BaseMessagingChannel):
    code = "mock"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.failures_remaining = 0

    def receive_event(self, payload: dict[str, Any]) -> dict[str, Any]: return dict(payload)
    def parse_message(self, event: dict[str, Any]) -> dict[str, Any]: return dict(event)

    def send_message(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise MessagingProviderError("Mock channel temporary failure")
        provider_id = f"mock_{uuid4().hex}"
        record = {**message, "provider_message_id": provider_id, "sent_at": datetime.now(UTC).isoformat()}
        self.sent.append(record)
        return {"status": "SENT", "provider_message_id": provider_id}

    def get_delivery_status(self, external_message_id: str) -> str:
        return "SENT" if any(item["provider_message_id"] == external_message_id for item in self.sent) else "UNKNOWN"


class WebChatAdapter(MockChannelAdapter):
    code = "website_chat"


class ChannelRegistry:
    def __init__(self) -> None:
        self.config = get_answer_bot_config()["channels"]
        self.adapters: dict[str, BaseMessagingChannel] = {"mock": MOCK_CHANNEL, "website_chat": WEB_CHANNEL}

    def register(self, adapter: BaseMessagingChannel) -> None: self.adapters[adapter.code] = adapter

    def get(self, channel: str) -> BaseMessagingChannel:
        channel = channel.lower()
        details = self.config.get(channel)
        if details is None: raise MessagingValidationError(f"Unsupported messaging channel {channel}")
        if not details.get("enabled") or channel not in self.adapters: raise MessagingValidationError(f"Messaging channel {channel} is {details.get('availability', 'not_configured')}")
        return self.adapters[channel]

    def status(self) -> list[dict[str, Any]]:
        return [{"channel": code, **details, "adapter_registered": code in self.adapters} for code, details in sorted(self.config.items())]


class WebhookSecurity:
    @staticmethod
    def verify(payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        supplied = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, supplied)


MOCK_CHANNEL = MockChannelAdapter()
WEB_CHANNEL = WebChatAdapter()
