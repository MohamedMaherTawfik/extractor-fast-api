"""Lazy probes for optional native runtime dependencies.

Native extension imports are intentionally kept out of general application
startup. A probe runs only when diagnostics or the related feature needs it,
and its result is cached for the lifetime of the backend process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any


@dataclass(frozen=True, slots=True)
class PyArrowRuntime:
    status: str
    table_type: Any | None = None
    parquet_writer_type: Any | None = None

    @property
    def available(self) -> bool:
        return self.table_type is not None and self.parquet_writer_type is not None


def _pyarrow_failure_status(exc: BaseException) -> str:
    message = str(exc).casefold()
    if "application control" in message or "code integrity" in message:
        return "BLOCKED_BY_WINDOWS_APPLICATION_CONTROL"
    if "dll load failed" in message:
        return "DLL_LOAD_FAILED"
    return "NOT_INSTALLED" if isinstance(exc, ModuleNotFoundError) else "IMPORT_FAILED"


@lru_cache(maxsize=1)
def load_pyarrow_runtime() -> PyArrowRuntime:
    """Load PyArrow on demand without making it a startup dependency."""

    try:
        pyarrow = import_module("pyarrow")
        parquet = import_module("pyarrow.parquet")
    except (ImportError, OSError) as exc:
        return PyArrowRuntime(status=_pyarrow_failure_status(exc))
    return PyArrowRuntime(
        status="AVAILABLE",
        table_type=pyarrow.Table,
        parquet_writer_type=parquet.ParquetWriter,
    )


def data_runtime_capabilities() -> dict[str, dict[str, object]]:
    """Return safe, non-secret status for optional data export support."""

    pyarrow = load_pyarrow_runtime()
    parquet_status = "AVAILABLE_VIA_PYARROW" if pyarrow.available else "NOT_AVAILABLE"
    return {
        "pyarrow": {
            "status": pyarrow.status,
            "required_at_startup": False,
        },
        "parquet": {
            "available": pyarrow.available,
            "status": parquet_status,
            "strategy": parquet_status,
        },
    }
