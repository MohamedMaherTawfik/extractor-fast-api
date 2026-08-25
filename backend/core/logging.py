"""Central logging configuration."""

from logging.config import dictConfig

from backend.core.config import get_settings
from backend.core.paths import paths


def configure_logging() -> None:
    settings = get_settings()
    paths.ensure_runtime_directories()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": settings.log_level,
                },
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": settings.log_level,
                    "filename": str(paths.backend_log_file),
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": settings.log_level,
            },
        }
    )
