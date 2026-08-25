"""Persistence operations for import audit batches and row errors."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.enums import ImportStatus
from backend.db.models.import_batch import CreatorImportBatch, CreatorImportError


class CreatorImportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(self, *, batch_uid: str, source_file: str) -> CreatorImportBatch:
        batch = CreatorImportBatch(
            batch_uid=batch_uid,
            source_file=source_file,
            status=ImportStatus.RUNNING,
        )
        self._session.add(batch)
        self._session.flush()
        return batch

    def add_error(
        self,
        *,
        batch_id: int,
        row_number: int,
        raw_data: dict[str, Any],
        error_type: str,
        error_message: str,
    ) -> CreatorImportError:
        error = CreatorImportError(
            batch_id=batch_id,
            row_number=row_number,
            raw_data=raw_data,
            error_type=error_type,
            error_message=error_message,
        )
        self._session.add(error)
        self._session.flush()
        return error

    def get(self, batch_id: int) -> CreatorImportBatch | None:
        statement = (
            select(CreatorImportBatch)
            .where(CreatorImportBatch.id == batch_id)
            .options(selectinload(CreatorImportBatch.errors))
        )
        return self._session.scalar(statement)
