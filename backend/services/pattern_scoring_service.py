"""Config-driven operational ranking for explainable patterns."""

from dataclasses import dataclass
from statistics import pstdev

from backend.services.pattern_config import PatternConfig, load_pattern_config


@dataclass(frozen=True)
class PatternScore:
    support_score: float
    confidence_score: float
    performance_score: float
    consistency_score: float
    recency_score: float
    pattern_score: float


class PatternScoringService:
    """The result is an operational rank, never a causal or scientific truth."""

    def __init__(self, config: PatternConfig | None = None) -> None:
        self.config = config or load_pattern_config()

    def score(
        self,
        *,
        support_ratio: float,
        confidences: list[float],
        performance_association: float | None,
        recency_score: float,
    ) -> PatternScore:
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        consistency = max(0.0, 1.0 - pstdev(confidences)) if len(confidences) > 1 else confidence
        performance = (
            min(1.0, abs(performance_association))
            if performance_association is not None
            else 0.0
        )
        components = {
            "support": min(1.0, max(0.0, support_ratio)),
            "confidence": min(1.0, max(0.0, confidence)),
            "performance": performance,
            "consistency": min(1.0, max(0.0, consistency)),
            "recency": min(1.0, max(0.0, recency_score)),
        }
        weights = self.config.score_weights
        total_weight = sum(weights.values())
        total = sum(components.get(name, 0.0) * weight for name, weight in weights.items()) / total_weight
        return PatternScore(
            support_score=round(components["support"], 6),
            confidence_score=round(components["confidence"], 6),
            performance_score=round(components["performance"], 6),
            consistency_score=round(components["consistency"], 6),
            recency_score=round(components["recency"], 6),
            pattern_score=round(total, 6),
        )

