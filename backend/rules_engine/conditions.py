"""Safe structured condition evaluation with explicit unknown semantics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.core.enums import RuleScopeStatus, TruthValue
from backend.core.exceptions import RuleValidationError


MISSING = object()
UNKNOWN_MARKERS = {"UNKNOWN", "MISSING_REQUIRED"}
NOT_APPLICABLE_MARKERS = {"NOT_APPLICABLE"}


class SafeFieldResolver:
    """Resolve mapping paths only beneath explicitly approved context roots."""

    DEFAULT_ROOTS = {
        "global", "project", "project_id", "task", "command", "content_type", "platform",
        "platform_profile", "brand", "brand_id", "brand_profile", "brand_version",
        "character", "character_id", "character_profile", "character_version",
        "product", "product_id", "product_context", "recipe", "recipe_id",
        "recipe_version", "content_dna", "audience", "language", "country",
        "category", "campaign", "recipe_type", "workflow_stage", "stage",
        "risk_level", "organic_paid", "accessibility", "accessibility_profile",
        "rights", "rights_profile", "risk_profile", "performance_context",
        "external_context", "external_business_context", "user_constraints",
        "system_constraints", "evidence", "output", "analysis", "facts",
        "technical", "visual", "audio", "copy", "seo", "qa", "capabilities",
        "_confidence",
    }

    def __init__(self, allowed_roots: set[str] | None = None) -> None:
        self.allowed_roots = allowed_roots or self.DEFAULT_ROOTS

    def resolve(self, context: Mapping[str, Any], path: str) -> Any:
        parts = path.split(".")
        if not parts or parts[0] not in self.allowed_roots or any(
            not part or part.startswith("_") and part != "_confidence" or "__" in part
            for part in parts
        ):
            raise RuleValidationError(f"Field path is not allowed: {path}")
        current: Any = context
        for part in parts:
            if not isinstance(current, Mapping) or part not in current:
                return MISSING
            current = current[part]
        return current


@dataclass(frozen=True)
class ConditionOutcome:
    value: TruthValue
    fields: tuple[str, ...]
    missing_fields: tuple[str, ...]


class StructuredConditionEvaluator:
    """Evaluate controlled trees; no source text is ever executed."""

    def __init__(
        self,
        resolver: SafeFieldResolver | None = None,
        *,
        allowed_patterns: dict[str, str] | None = None,
    ) -> None:
        self.resolver = resolver or SafeFieldResolver()
        self.allowed_patterns = allowed_patterns or {
            "HEX_COLOR": r"#[0-9A-Fa-f]{6}",
            "LANGUAGE_TAG": r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*",
            "SAFE_IDENTIFIER": r"[A-Za-z][A-Za-z0-9_-]{0,99}",
        }

    def evaluate(self, tree: dict[str, Any], context: Mapping[str, Any]) -> ConditionOutcome:
        value, fields, missing = self._evaluate(tree, context, 0)
        return ConditionOutcome(value, tuple(dict.fromkeys(fields)), tuple(dict.fromkeys(missing)))

    def _evaluate(self, node: Any, context: Mapping[str, Any], depth: int):
        if depth > 20 or not isinstance(node, dict):
            raise RuleValidationError("Invalid or overly deep condition tree")
        if "all" in node:
            children = self._children(node, "all")
            results = [self._evaluate(child, context, depth + 1) for child in children]
            return self._combine_all(results)
        if "any" in node:
            children = self._children(node, "any")
            results = [self._evaluate(child, context, depth + 1) for child in children]
            return self._combine_any(results)
        if "not" in node:
            if set(node) != {"not"}:
                raise RuleValidationError("not node cannot contain extra keys")
            child = node["not"]
            if isinstance(child, list):
                if len(child) != 1:
                    raise RuleValidationError("not accepts exactly one condition")
                child = child[0]
            value, fields, missing = self._evaluate(child, context, depth + 1)
            inverted = {TruthValue.TRUE: TruthValue.FALSE, TruthValue.FALSE: TruthValue.TRUE}.get(value, TruthValue.UNKNOWN)
            return inverted, fields, missing
        return self._leaf(node, context)

    @staticmethod
    def _children(node: dict[str, Any], key: str) -> list[dict[str, Any]]:
        if set(node) != {key} or not isinstance(node[key], list) or not node[key]:
            raise RuleValidationError(f"{key} requires a non-empty condition list")
        return node[key]

    def _leaf(self, node: dict[str, Any], context: Mapping[str, Any]):
        if set(node) - {"field", "operator", "value"}:
            raise RuleValidationError("Condition leaf contains unsupported keys")
        field = node.get("field")
        operator = node.get("operator")
        if not isinstance(field, str) or operator not in {
            "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "IN", "NOT_IN",
            "EXISTS", "NOT_EXISTS", "CONTAINS", "MATCHES_ALLOWED_PATTERN",
        }:
            raise RuleValidationError("Condition leaf uses an invalid field or operator")
        actual = self.resolver.resolve(context, field)
        missing = actual is MISSING or actual is None or (
            isinstance(actual, str) and actual.upper() in UNKNOWN_MARKERS | NOT_APPLICABLE_MARKERS
        )
        if operator == "EXISTS":
            return (TruthValue.FALSE if missing else TruthValue.TRUE), [field], ([field] if missing else [])
        if operator == "NOT_EXISTS":
            return (TruthValue.TRUE if missing else TruthValue.FALSE), [field], ([field] if missing else [])
        if missing:
            return TruthValue.UNKNOWN, [field], [field]
        expected = node.get("value")
        try:
            matched = self._compare(operator, actual, expected)
        except (TypeError, ValueError):
            return TruthValue.UNKNOWN, [field], [field]
        return (TruthValue.TRUE if matched else TruthValue.FALSE), [field], []

    def _compare(self, operator: str, actual: Any, expected: Any) -> bool:
        if operator == "EQ": return actual == expected
        if operator == "NEQ": return actual != expected
        if operator == "GT": return actual > expected
        if operator == "GTE": return actual >= expected
        if operator == "LT": return actual < expected
        if operator == "LTE": return actual <= expected
        if operator == "IN": return actual in expected
        if operator == "NOT_IN": return actual not in expected
        if operator == "CONTAINS": return expected in actual
        if operator == "MATCHES_ALLOWED_PATTERN":
            import re
            pattern = self.allowed_patterns.get(str(expected))
            if pattern is None:
                raise RuleValidationError("Pattern name is not allowlisted")
            return re.fullmatch(pattern, str(actual)) is not None
        raise RuleValidationError("Unsupported condition operator")

    @staticmethod
    def _combine_all(results):
        fields = sum((item[1] for item in results), [])
        missing = sum((item[2] for item in results), [])
        if any(item[0] is TruthValue.FALSE for item in results):
            return TruthValue.FALSE, fields, missing
        if any(item[0] is TruthValue.UNKNOWN for item in results):
            return TruthValue.UNKNOWN, fields, missing
        return TruthValue.TRUE, fields, missing

    @staticmethod
    def _combine_any(results):
        fields = sum((item[1] for item in results), [])
        missing = sum((item[2] for item in results), [])
        if any(item[0] is TruthValue.TRUE for item in results):
            return TruthValue.TRUE, fields, missing
        if any(item[0] is TruthValue.UNKNOWN for item in results):
            return TruthValue.UNKNOWN, fields, missing
        return TruthValue.FALSE, fields, missing


class RuleScopeMatcher:
    def __init__(self, resolver: SafeFieldResolver | None = None) -> None:
        self.resolver = resolver or SafeFieldResolver()

    def match(self, scope: Mapping[str, Any], context: Mapping[str, Any]) -> RuleScopeStatus:
        partial = False
        for field, expected in scope.items():
            actual = self.resolver.resolve(context, field)
            if actual is MISSING or actual is None or str(actual).upper() == "UNKNOWN":
                partial = True
                continue
            allowed = expected if isinstance(expected, list) else [expected]
            if actual not in allowed:
                return RuleScopeStatus.NOT_APPLICABLE
        return RuleScopeStatus.PARTIAL_CONTEXT if partial else RuleScopeStatus.APPLICABLE
