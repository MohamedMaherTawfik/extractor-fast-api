"""Persistent job repository for collection runs."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.enums import CollectionRunStatus
from backend.db.models.collection_run import CollectionRun


class CollectionRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        connector: str,
        options: dict,
        creator_id: int | None = None,
        platform_account_id: int | None = None,
        source_url: str | None = None,
    ) -> CollectionRun:
        run = CollectionRun(
            job_uid=f"JOB_{uuid4().hex.upper()}",
            creator_id=creator_id,
            platform_account_id=platform_account_id,
            connector=connector,
            source_url=source_url,
            options=options,
            status=CollectionRunStatus.QUEUED,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def get(self, run_id: int) -> CollectionRun | None:
        return self._session.get(CollectionRun, run_id)

    def list(self, *, offset: int = 0, limit: int = 100) -> list[CollectionRun]:
        statement = (
            select(CollectionRun)
            .order_by(CollectionRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def set_status(
        self,
        run: CollectionRun,
        status: CollectionRunStatus,
    ) -> CollectionRun:
        run.status = status
        self._session.flush()
        return run
