"""HTTP translation for domain exceptions."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import (
    ConflictError,
    ImportValidationError,
    InvalidAccountError,
    ContentNormalizationError,
    AnalysisError,
    RuleValidationError,
    GenerationError,
    SalesValidationError,
    MessagingValidationError,
    MessagingProviderError,
    NormalizationError,
    NotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(
        request: Request,
        exc: ConflictError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    async def validation_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.add_exception_handler(NormalizationError, validation_handler)
    app.add_exception_handler(ImportValidationError, validation_handler)
    app.add_exception_handler(InvalidAccountError, validation_handler)
    app.add_exception_handler(ContentNormalizationError, validation_handler)
    app.add_exception_handler(AnalysisError, validation_handler)
    app.add_exception_handler(RuleValidationError, validation_handler)
    app.add_exception_handler(GenerationError, validation_handler)
    app.add_exception_handler(SalesValidationError, validation_handler)
    app.add_exception_handler(MessagingValidationError, validation_handler)
    app.add_exception_handler(MessagingProviderError, validation_handler)
