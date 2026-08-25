"""Queue-neutral job abstraction with a local inline executor."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(slots=True)
class Job:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.QUEUED
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None


JobHandler = Callable[[dict[str, Any]], Any]


class JobExecutor(ABC):
    """Execution boundary that a future queue adapter can replace."""

    @abstractmethod
    def submit(self, job: Job, handler: JobHandler) -> Job:
        """Submit a job and return its latest state."""


class InlineJobExecutor(JobExecutor):
    """Synchronous local executor used until a real queue is introduced."""

    def submit(self, job: Job, handler: JobHandler) -> Job:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        try:
            job.result = handler(job.payload)
            job.status = JobStatus.COMPLETED
        except Exception as exc:
            job.error = str(exc)
            job.status = JobStatus.FAILED
        finally:
            job.finished_at = datetime.now(UTC)
        return job
