"""Provider-neutral conversation model interface with a local deterministic default."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConversationModelProvider(ABC):
    code: str
    locality: str

    @abstractmethod
    def classify(self, text: str, taxonomy: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def generate(self, prompt: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def summarize(self, messages: list[dict[str, Any]]) -> dict[str, Any]: ...
    @abstractmethod
    def tool_plan(self, request: dict[str, Any]) -> dict[str, Any]: ...


class DeterministicLocalConversationProvider(ConversationModelProvider):
    code = "deterministic_local"
    locality = "local"

    def classify(self, text: str, taxonomy: dict[str, Any]) -> dict[str, Any]: return {"provider": self.code, "text_length": len(text)}
    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]: return {"provider": self.code, "entities": []}
    def generate(self, prompt: dict[str, Any]) -> dict[str, Any]: return {"provider": self.code, "text": prompt.get("draft_text", "")}
    def summarize(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        text = " | ".join(str(item.get("text") or "")[:200] for item in messages[-8:])
        return {"provider": self.code, "summary": text[:1200]}
    def tool_plan(self, request: dict[str, Any]) -> dict[str, Any]: return {"provider": self.code, "tools": request.get("allowed_tools", [])}


class ProviderRegistry:
    def __init__(self) -> None: self.providers = {"deterministic_local": DeterministicLocalConversationProvider()}
    def get(self, code: str, privacy_mode: str = "LOCAL_ONLY") -> ConversationModelProvider:
        provider = self.providers[code]
        if privacy_mode == "LOCAL_ONLY" and provider.locality != "local": raise ValueError("Cloud provider forbidden in LOCAL_ONLY mode")
        return provider
