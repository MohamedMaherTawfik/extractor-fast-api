"""Central project path manager.

Every project path is derived from this file's location. No machine-specific
path is stored in source or configuration.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Self


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """All filesystem locations owned by the application."""

    project_root: Path
    data: Path
    database: Path
    models: Path
    assets: Path
    rules: Path
    taxonomy: Path
    logs: Path
    configs: Path
    connector_configs: Path
    imports: Path
    raw: Path
    media: Path
    generated_assets: Path
    reference_assets: Path
    provider_responses: Path
    migrations: Path
    database_file: Path
    config_file: Path
    env_file: Path
    backend_log_file: Path
    alembic_config_file: Path

    @classmethod
    def discover(cls) -> Self:
        project_root = Path(__file__).resolve().parents[2]
        database = project_root / "database"
        configs = project_root / "configs"
        logs = project_root / "logs"
        migrations = database / "migrations"
        return cls(
            project_root=project_root,
            data=project_root / "data",
            database=database,
            models=project_root / "models",
            assets=project_root / "assets",
            rules=project_root / "rules",
            taxonomy=project_root / "taxonomy",
            logs=logs,
            configs=configs,
            connector_configs=configs / "connectors",
            imports=project_root / "data" / "imports",
            raw=project_root / "data" / "raw",
            media=project_root / "data" / "media",
            generated_assets=project_root / "data" / "assets" / "generated",
            reference_assets=project_root / "data" / "assets" / "references",
            provider_responses=project_root / "data" / "provider_responses",
            migrations=migrations,
            database_file=database / "emy_private_ai_os.db",
            config_file=configs / "app.yaml",
            env_file=project_root / ".env",
            backend_log_file=logs / "backend.log",
            alembic_config_file=project_root / "alembic.ini",
        )

    def ensure_runtime_directories(self) -> None:
        for directory in (
            self.data,
            self.database,
            self.models,
            self.assets,
            self.rules,
            self.taxonomy,
            self.logs,
            self.configs,
            self.connector_configs,
            self.imports,
            self.raw,
            self.media,
            self.generated_assets,
            self.reference_assets,
            self.provider_responses,
            self.migrations,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def resolve_under(self, base: Path, relative_path: str | Path) -> Path:
        """Resolve a relative path while preventing traversal outside base."""

        base = base.resolve()
        candidate = (base / relative_path).resolve()
        if not candidate.is_relative_to(base):
            raise ValueError("Path must remain inside its configured project directory")
        return candidate

    def relative(self, path: Path) -> Path:
        """Return a project-relative representation for display or storage."""

        return path.resolve().relative_to(self.project_root)

    @staticmethod
    def validate_storage_value(value: str) -> str:
        """Normalize and validate a path before storing it in the database."""

        if PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
            raise ValueError("Stored file paths must be project-relative")
        normalized = PurePosixPath(value.replace("\\", "/"))
        if ".." in normalized.parts:
            raise ValueError("Stored file paths cannot traverse parent directories")
        return normalized.as_posix()

    @staticmethod
    def safe_component(value: str) -> str:
        """Return a conservative filesystem component for managed storage."""

        cleaned = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in value.strip()
        ).strip("_")
        if not cleaned:
            raise ValueError("Storage path component cannot be empty")
        return cleaned[:150]


paths = ProjectPaths.discover()
