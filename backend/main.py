"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.errors import register_exception_handlers
from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.db.session import init_database


settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_database()
    getLogger(__name__).info("%s started in %s mode", settings.app_name, settings.environment)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:1420", "http://localhost:1420", "http://tauri.localhost", "tauri://localhost"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
app.include_router(api_router)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
