"""Read-only system discovery endpoints for the desktop operator UI."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.services.operator_service import OperatorService


router = APIRouter(prefix="/system", tags=["operator-control-center"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/capabilities")
def capabilities(session: DatabaseSession): return OperatorService(session).capabilities()


@router.get("/health-detail")
def health_detail(session: DatabaseSession): return OperatorService(session).health()


@router.get("/dashboard")
def dashboard(session: DatabaseSession): return OperatorService(session).repository.dashboard()


@router.get("/notifications")
def notifications(session: DatabaseSession, limit: int = Query(20, ge=1, le=100)): return OperatorService(session).repository.notifications(limit=limit)


@router.get("/search")
def global_search(session: DatabaseSession, q: str = Query(min_length=2, max_length=100), limit: int = Query(24, ge=1, le=100)): return OperatorService(session).repository.search(q, limit=limit)


@router.get("/workspaces/{name}")
def workspace(name: str, session: DatabaseSession, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)): return OperatorService(session).workspace(name, offset, limit)


@router.get("/settings")
def safe_settings(session: DatabaseSession): return OperatorService(session).settings_view()
