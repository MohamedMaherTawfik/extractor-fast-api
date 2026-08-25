"""Lead source, run, canonical result, control, and export APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db, session_scope
from backend.leads.service import LeadAcquisitionService
from backend.leads.storage import LeadExportService
from backend.repositories.lead_repository import LeadRepository
from backend.schemas.leads import LeadExportRequest, LeadRunRequest


router = APIRouter(tags=["lead-data-acquisition"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _execute_background(run_uid: str) -> None:
    with session_scope() as session:
        LeadAcquisitionService(session).execute_run(run_uid)


@router.get("/lead-sources")
def lead_sources(session: DatabaseSession):
    rows = LeadAcquisitionService(session).sync_sources()
    return [{column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "id"} for row in rows]


@router.get("/lead-control")
def lead_control(session: DatabaseSession):
    return LeadAcquisitionService(session).control_options()


@router.post("/lead-control/workbook/import", status_code=status.HTTP_201_CREATED)
async def import_lead_workbook(session: DatabaseSession, file: UploadFile = File(...)):
    content = await file.read()
    try:
        return LeadAcquisitionService(session).workbook.import_bytes(file.filename or "workbook.xlsx", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/lead-runs", status_code=status.HTTP_201_CREATED)
def create_lead_run(request: LeadRunRequest, background: BackgroundTasks, session: DatabaseSession):
    service = LeadAcquisitionService(session)
    try:
        result = service.create_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if request.dry_run:
        return result
    session.commit()
    response = service.get_run(result.run_uid)
    if request.execute:
        background.add_task(_execute_background, result.run_uid)
    return response


@router.get("/lead-runs")
def list_lead_runs(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    return LeadAcquisitionService(session).list_runs(offset, limit)


@router.get("/lead-runs/{run_uid}")
def get_lead_run(run_uid: str, session: DatabaseSession):
    return LeadAcquisitionService(session).get_run(run_uid)


@router.post("/lead-runs/{run_uid}/pause")
def pause_lead_run(run_uid: str, session: DatabaseSession):
    try:
        run = LeadAcquisitionService(session).pause(run_uid)
        return LeadAcquisitionService.run_dict(run, include_jobs=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/lead-runs/{run_uid}/resume")
def resume_lead_run(run_uid: str, background: BackgroundTasks, session: DatabaseSession):
    service = LeadAcquisitionService(session)
    try:
        run = service.resume(run_uid)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    response = service.get_run(run_uid)
    background.add_task(_execute_background, run_uid)
    return response


@router.post("/lead-runs/{run_uid}/cancel")
def cancel_lead_run(run_uid: str, session: DatabaseSession):
    try:
        run = LeadAcquisitionService(session).cancel(run_uid)
        return LeadAcquisitionService.run_dict(run, include_jobs=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/lead-runs/{run_uid}/retry")
def retry_lead_run(run_uid: str, background: BackgroundTasks, session: DatabaseSession):
    service = LeadAcquisitionService(session)
    try:
        service.retry(run_uid)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    response = service.get_run(run_uid)
    background.add_task(_execute_background, run_uid)
    return response


@router.post("/leads/export")
def export_leads(request: LeadExportRequest, session: DatabaseSession):
    target = LeadExportService(LeadRepository(session)).export(request)
    media = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "parquet": "application/vnd.apache.parquet",
    }[request.format]
    return FileResponse(target, media_type=media, filename=target.name)


@router.get("/leads")
def list_leads(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    fit_class: str | None = None,
    governorate: str | None = None,
    category: str | None = None,
    source: str | None = None,
    verified_only: bool = False,
    q: Annotated[str | None, Query(max_length=200)] = None,
):
    return LeadAcquisitionService(session).list_leads(
        offset=offset,
        limit=limit,
        fit_class=fit_class,
        governorate=governorate,
        category=category,
        source=source,
        verified_only=verified_only,
        query=q,
    )


@router.get("/leads/{lead_uid}")
def get_lead(lead_uid: str, session: DatabaseSession):
    return LeadAcquisitionService(session).get_lead(lead_uid)


@router.get("/lead-stats")
def lead_stats(session: DatabaseSession):
    return LeadAcquisitionService(session).stats()

