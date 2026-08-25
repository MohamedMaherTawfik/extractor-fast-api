from sqlalchemy import inspect

from backend.core.paths import paths
from backend.db.session import engine, init_database, session_scope
from backend.repositories.system_meta_repository import SystemMetaRepository


def test_database_connection_and_system_meta_table() -> None:
    init_database()

    assert paths.database_file.is_file()
    assert "system_meta" in inspect(engine).get_table_names()

    with session_scope() as session:
        version = SystemMetaRepository(session).get_by_key("application_version")

    assert version is not None
    assert version.value == "0.1.0"
