"""Replaceable generation contracts without model bindings."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class GeneratorBackend(StrEnum):
    LOCAL_MODEL = "local_model"
    EXTERNAL_API = "external_api"
    CUSTOM_MODEL = "custom_model"


class GenerationResult(BaseModel):
    output: Any
    backend: GeneratorBackend
    provider: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseGenerator(ABC):
    output_type: ClassVar[str]

    def __init__(self, backend: GeneratorBackend) -> None:
        self.backend = backend

    @abstractmethod
    def generate(self, request: Mapping[str, Any]) -> GenerationResult:
        """Generate an output using the configured replaceable backend."""


class ImageGenerator(BaseGenerator):
    output_type = "image"


class VideoGenerator(BaseGenerator):
    output_type = "video"


class CopyGenerator(BaseGenerator):
    output_type = "copy"
