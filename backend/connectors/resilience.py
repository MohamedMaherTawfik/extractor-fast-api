"""Reusable rate limiting and bounded retry policies for connectors."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from backend.core.exceptions import (
    ConnectorPermissionError,
    ConnectorRateLimitError,
    ConnectorTemporaryError,
    InvalidAccountError,
)


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    initial_delay: float
    max_delay: float
    sleep: Callable[[float], None] = time.sleep

    def run(
        self,
        operation: Callable[[], T],
        on_retry: Callable[[int, float, Exception], None] | None = None,
    ) -> T:
        attempt = 0
        while True:
            try:
                return operation()
            except (ConnectorPermissionError, InvalidAccountError):
                raise
            except ConnectorTemporaryError as exc:
                attempt = self._retry(attempt, exc, on_retry)
            except Exception as exc:
                attempt = self._retry(attempt, exc, on_retry)

    def _retry(
        self,
        attempt: int,
        exc: Exception,
        on_retry: Callable[[int, float, Exception], None] | None,
    ) -> int:
        if attempt >= self.max_retries:
            raise exc
        delay = min(self.initial_delay * (2**attempt), self.max_delay)
        if isinstance(exc, ConnectorRateLimitError) and exc.retry_after is not None:
            delay = min(max(exc.retry_after, 0), self.max_delay)
        attempt += 1
        if on_retry:
            on_retry(attempt, delay, exc)
        self.sleep(delay)
        return attempt


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._minimum_interval = 60 / requests_per_minute
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None

    def acquire(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            remaining = self._minimum_interval - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last_request_at = now
