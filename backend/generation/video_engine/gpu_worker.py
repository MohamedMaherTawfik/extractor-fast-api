"""Bounded local worker queue for serial or low-concurrency GPU execution."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from typing import Callable


class GPUWorker:
    def __init__(self, concurrency: int = 1) -> None:
        self._executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="emy-video-gpu")
        self._futures: dict[str, Future[None]] = {}
        self._cancelled: set[str] = set()
        self._lock = RLock()

    def submit(self, job_id: str, task: Callable[[], None]) -> None:
        with self._lock:
            current = self._futures.get(job_id)
            if current and not current.done():
                return
            self._cancelled.discard(job_id)
            self._futures[job_id] = self._executor.submit(task)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            self._cancelled.add(job_id)
            future = self._futures.get(job_id)
            return bool(future.cancel()) if future else True

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def active_jobs(self) -> list[str]:
        with self._lock:
            return [job_id for job_id, future in self._futures.items() if not future.done()]

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)
