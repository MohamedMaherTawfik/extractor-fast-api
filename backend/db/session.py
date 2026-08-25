"""SQLite engine and session lifecycle."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings
from backend.core.paths import paths
from backend.db.migrations import CURRENT_SCHEMA_REVISION, upgrade_database


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.database_echo,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@contextmanager
def session_scope() -> Iterator[Session]:
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def init_database() -> None:
    from backend.repositories.system_meta_repository import SystemMetaRepository

    upgrade_database()
    with session_scope() as session:
        repository = SystemMetaRepository(session)
        repository.set("schema_version", CURRENT_SCHEMA_REVISION)
        repository.set("application_version", settings.version)
