"""Application health orchestration."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.config import Settings
from backend.repositories.system_meta_repository import SystemMetaRepository
from backend.schemas.health import HealthResponse


class HealthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._repository = SystemMetaRepository(session)
        self._settings = settings

    def get_status(self) -> HealthResponse:
        try:
            database_ok = self._repository.health_check()
        except SQLAlchemyError:
            database_ok = False
        return HealthResponse(
            status="ok" if database_ok else "degraded",
            database="ok" if database_ok else "error",
            environment=self._settings.environment,
            version=self._settings.version,
        )
