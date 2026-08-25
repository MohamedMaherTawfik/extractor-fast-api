"""Managed CSV/XLSX Creator Import API."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import ImportValidationError
from backend.db.session import get_db
from backend.schemas.imports import CreatorImportBatchResponse
from backend.services.creator_import_service import CreatorImportService


router = APIRouter(tags=["creator-imports"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/creator-imports",
    response_model=CreatorImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_creators(
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
    column_mapping: Annotated[str | None, Form()] = None,
):
    max_bytes = get_settings().import_max_file_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    mapping_overrides = None
    if column_mapping:
        try:
            mapping_overrides = json.loads(column_mapping)
        except json.JSONDecodeError as exc:
            raise ImportValidationError(
                "column_mapping must be valid JSON"
            ) from exc
        if not isinstance(mapping_overrides, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in mapping_overrides.items()
        ):
            raise ImportValidationError(
                "column_mapping must be a string-to-string object"
            )
    return CreatorImportService(session).import_bytes(
        filename=file.filename or "creator_import",
        content=content,
        mapping_overrides=mapping_overrides,
    )
