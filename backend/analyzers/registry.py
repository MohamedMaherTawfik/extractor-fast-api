"""Registry isolating analysis engine implementations from orchestration."""

from backend.analyzers.engine import AnalysisEngine, MetadataEngine, ObservationEngine
from backend.core.exceptions import AnalysisEngineError


DEFAULT_ENGINE_NAMES = (
    "video_structure",
    "vision",
    "audio",
    "speech",
    "ocr",
    "copy",
    "behavior",
    "seo",
)


class AnalysisEngineRegistry:
    def __init__(self, *, include_defaults: bool = True) -> None:
        self._engines: dict[str, AnalysisEngine] = {}
        if include_defaults:
            self.register(MetadataEngine())
            for name in DEFAULT_ENGINE_NAMES:
                self.register(ObservationEngine(name))

    def register(self, engine: AnalysisEngine) -> None:
        self._engines[engine.name] = engine

    def get(self, name: str) -> AnalysisEngine:
        try:
            return self._engines[name]
        except KeyError as exc:
            raise AnalysisEngineError(f"Analysis engine is not configured: {name}") from exc

    def model_version(self, names: set[str] | None = None) -> str:
        selected = names or set(self._engines)
        return "|".join(
            (
                f"{name}:{self._engines[name].version}"
                if name in self._engines
                else f"{name}:unconfigured"
            )
            for name in sorted(selected)
        )
