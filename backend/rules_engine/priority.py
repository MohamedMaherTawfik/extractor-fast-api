"""Configurable priority comparison kept separate from severity."""

from backend.core.enums import RuleHardness
from backend.services.rule_config import RuleEngineConfig, load_rule_config


class PriorityResolver:
    def __init__(self, config: RuleEngineConfig | None = None) -> None:
        self.config = config or load_rule_config()

    def rank(self, rule) -> tuple[int, int, str]:
        hardness = getattr(rule, "hardness", RuleHardness.SOFT)
        return (1 if hardness is RuleHardness.HARD else 0, int(rule.priority), getattr(rule, "rule_code", ""))

    def winner(self, first, second):
        return max((first, second), key=self.rank)
