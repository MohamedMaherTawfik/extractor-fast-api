"""Local health endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db.session import get_db
from backend.schemas.health import HealthResponse
from backend.services.health_service import HealthService


router = APIRouter(tags=["system"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/health", response_model=HealthResponse)
def health(session: DatabaseSession) -> HealthResponse:
    return HealthService(session, get_settings()).get_status()
