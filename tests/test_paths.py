import re
from pathlib import Path

from backend.core.paths import paths


def test_managed_paths_are_inside_project_root() -> None:
    managed_paths = (
        paths.data,
        paths.database,
        paths.models,
        paths.assets,
        paths.rules,
        paths.taxonomy,
        paths.logs,
        paths.configs,
        paths.connector_configs,
        paths.creator_discovery,
        paths.creator_discovery_exports,
        paths.creator_discovery_imports,
        paths.imports,
        paths.raw,
        paths.media,
        paths.migrations,
        paths.database_file,
        paths.config_file,
        paths.env_file,
        paths.backend_log_file,
        paths.alembic_config_file,
    )

    assert all(path.is_relative_to(paths.project_root) for path in managed_paths)


def test_path_manager_source_has_no_hardcoded_windows_path() -> None:
    source = Path("backend/core/paths.py").read_text(encoding="utf-8")

    assert re.search(r"[A-Za-z]:\\", source) is None
