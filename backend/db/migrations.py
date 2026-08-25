"""Programmatic Alembic entry points used by startup and tests."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.core.config import get_settings
from backend.core.paths import paths


INITIAL_REVISION = "0001_core"
CURRENT_SCHEMA_REVISION = "0009_answer_bot"


def get_alembic_config(database_url: str | None = None) -> Config:
    settings = get_settings()
    config = Config(str(paths.alembic_config_file))
    config.set_main_option("script_location", str(paths.migrations))
    config.set_main_option(
        "sqlalchemy.url",
        (database_url or settings.database_url).replace("%", "%%"),
    )
    return config


def upgrade_database(database_url: str | None = None) -> None:
    """Upgrade a fresh or legacy core database to the current revision."""

    settings = get_settings()
    url = database_url or settings.database_url
    paths.ensure_runtime_directories()
    config = get_alembic_config(url)

    probe_engine = create_engine(url)
    try:
        existing_tables = set(inspect(probe_engine).get_table_names())
    finally:
        probe_engine.dispose()

    if "system_meta" in existing_tables and "alembic_version" not in existing_tables:
        command.stamp(config, INITIAL_REVISION)
    command.upgrade(config, "head")
