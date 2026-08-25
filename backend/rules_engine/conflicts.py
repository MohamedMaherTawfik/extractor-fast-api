"""Explainable, deterministic constraint conflict resolution."""

from backend.core.enums import RuleHardness, RuleResultStatus
from backend.schemas.rules import RuleConflictResponse, RuleEvaluationItem
from backend.rules_engine.priority import PriorityResolver


class RuleConflictResolver:
    def __init__(self, priority: PriorityResolver | None = None) -> None:
        self.priority = priority or PriorityResolver()

    def resolve(self, results: list[RuleEvaluationItem]) -> list[RuleConflictResponse]:
        by_target: dict[str, list[RuleEvaluationItem]] = {}
        for result in results:
            if result.action.value not in {"set_constraint", "set_default"}:
                continue
            for field in result.affected_fields:
                by_target.setdefault(field, []).append(result)
        conflicts: list[RuleConflictResponse] = []
        for target, candidates in by_target.items():
            values = {self._stable_value(candidate.suggested_value) for candidate in candidates}
            if len(values) < 2:
                continue
            ranked = sorted(candidates, key=self.priority.rank, reverse=True)
            first, second = ranked[:2]
            same_hard_priority = (
                first.hardness is RuleHardness.HARD
                and second.hardness is RuleHardness.HARD
                and first.priority == second.priority
            )
            if same_hard_priority:
                first.result = RuleResultStatus.CONFLICT_REQUIRES_RESOLUTION
                second.result = RuleResultStatus.CONFLICT_REQUIRES_RESOLUTION
                first.human_review_required = second.human_review_required = True
                conflicts.append(RuleConflictResponse(
                    rule_codes=[item.rule_code for item in ranked], target=target,
                    reason="Equal-priority hard constraints disagree",
                    requires_human_review=True,
                ))
            else:
                conflicts.append(RuleConflictResponse(
                    winner_rule_code=first.rule_code,
                    loser_rule_code=second.rule_code,
                    rule_codes=[item.rule_code for item in ranked], target=target,
                    reason="Higher hardness and priority wins deterministically",
                ))
                for loser in ranked[1:]:
                    loser.result = RuleResultStatus.FAIL
                    loser.reason = f"Superseded by {first.rule_code} for {target}"
        return conflicts

    @staticmethod
    def _stable_value(value) -> str:
        import json
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
