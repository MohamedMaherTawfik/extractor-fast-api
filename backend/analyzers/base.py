"""Media analyzer contracts without AI implementations."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator


class AnalysisTimeRange(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "AnalysisTimeRange":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class AnalysisResult(BaseModel):
    result: Any
    confidence: float = Field(ge=0, le=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    source: str
    timestamp: datetime | None = None
    time_range: AnalysisTimeRange | None = None


class BaseAnalyzer(ABC):
    media_type: ClassVar[str]

    @abstractmethod
    def analyze(
        self,
        content: Mapping[str, Any],
        extraction_rules: Mapping[str, Any],
    ) -> AnalysisResult:
        """Analyze canonical content according to external extraction rules."""


class VideoAnalyzer(BaseAnalyzer):
    media_type = "video"


class ImageAnalyzer(BaseAnalyzer):
    media_type = "image"


class AudioAnalyzer(BaseAnalyzer):
    media_type = "audio"


class TextAnalyzer(BaseAnalyzer):
    media_type = "text"


class CarouselAnalyzer(BaseAnalyzer):
    media_type = "carousel"
