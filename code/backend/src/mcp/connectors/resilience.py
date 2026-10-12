"""Timeout + retry + a small circuit breaker around each source, so one
source going down never blocks the other's data."""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger("connectors")


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_after_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self._failures = 0
        self._open_since: float | None = None

    def is_open(self) -> bool:
        if self._open_since is None:
            return False
        if time.monotonic() - self._open_since >= self.reset_after_seconds:
            self._open_since = None  # half-open: allow a trial call
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._open_since = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._open_since = time.monotonic()


async def call_resilient(
    fn, *, source: str, breaker: CircuitBreaker,
    timeout_seconds: float = 300.0, max_retries: int = 2, backoff_seconds: float = 0.5,
    default=None,
):
    """Runs `fn()` with timeout + retry, tracks the breaker, never raises.
    Returns (result, error_message)."""
    if breaker.is_open():
        msg = f"{source}: circuit open, skipping"
        log.warning(msg)
        return default, msg

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_seconds)
            breaker.record_success()
            return result, None
        except Exception as exc:  # noqa: BLE001 - a source can fail however it wants
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning("%s: attempt %d failed — %s", source, attempt + 1, last_error)
            if attempt < max_retries:
                await asyncio.sleep(backoff_seconds * (2 ** attempt))

    breaker.record_failure()
    return default, last_error
