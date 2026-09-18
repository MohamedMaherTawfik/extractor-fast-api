"""Durable database-backed creator discovery execution outside HTTP requests."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

from sqlalchemy import select

from backend.creator_discovery.service import CreatorDiscoveryService
from backend.db.models.creator_discovery import CreatorDiscoveryRun
from backend.db.session import session_scope


class CreatorDiscoveryWorker:
    """Single-process worker with database checkpoints and restart recovery."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="creator-discovery")
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()
        self._closed = False

    def enqueue(self, run_uid: str) -> None:
        with self._lock:
            if self._closed:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="creator-discovery")
                self._closed = False
            current = self._futures.get(run_uid)
            if current is not None and not current.done():
                return
            self._futures[run_uid] = self._executor.submit(self._execute, run_uid)

    def recover(self) -> None:
        # Lifespan startup can be entered more than once by embedded clients and
        # test harnesses. A locally active future is not a crashed job and must
        # never be rewound to PENDING while it is committing checkpoints.
        with self._lock:
            active_run_uids = {
                run_uid for run_uid, future in self._futures.items()
                if not future.done()
            }
        with session_scope() as session:
            runs = list(session.scalars(
                select(CreatorDiscoveryRun).where(
                    CreatorDiscoveryRun.status.in_(["PENDING", "RUNNING"]),
                )
            ))
            for run in runs:
                if run.run_uid in active_run_uids:
                    continue
                if run.status == "RUNNING":
                    run.status = "PENDING"
                for job in run.jobs:
                    if job.status == "RUNNING":
                        job.status = "PENDING"
                        job.checkpoint = {
                            **(job.checkpoint or {}),
                            "stage": "PENDING",
                            "progress_percent": min(float((job.checkpoint or {}).get("progress_percent") or 0), 95),
                        }
            run_uids = [
                run.run_uid for run in runs
                if run.run_uid not in active_run_uids
            ]
        for run_uid in run_uids:
            self.enqueue(run_uid)

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            executor = self._executor
        executor.shutdown(wait=False, cancel_futures=False)

    def _execute(self, run_uid: str) -> None:
        try:
            with session_scope() as session:
                CreatorDiscoveryService(session).execute_run(run_uid)
        finally:
            with self._lock:
                self._futures.pop(run_uid, None)


creator_discovery_worker = CreatorDiscoveryWorker()


def enqueue_creator_discovery(run_uid: str) -> None:
    creator_discovery_worker.enqueue(run_uid)
