"""Deterministic dependency ordering and cycle rejection."""

from backend.core.exceptions import RuleDependencyCycleError


class RuleDependencyGraph:
    def order(self, versions: list) -> list:
        by_code = {version.rule.rule_code: version for version in versions}
        graph = {
            code: {dependency.depends_on_rule.rule_code for dependency in version.dependencies if dependency.depends_on_rule.rule_code in by_code}
            for code, version in by_code.items()
        }
        ordered: list = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(code: str) -> None:
            if code in permanent:
                return
            if code in temporary:
                raise RuleDependencyCycleError("RULE_DEPENDENCY_CYCLE")
            temporary.add(code)
            for dependency in sorted(graph[code]):
                visit(dependency)
            temporary.remove(code)
            permanent.add(code)
            ordered.append(by_code[code])

        for code in sorted(graph):
            visit(code)
        return ordered
