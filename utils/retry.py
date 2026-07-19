from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    delay_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("Retry attempts must be at least 1.")
        if self.delay_seconds < 0:
            raise ValueError("Retry delay cannot be negative.")


def retry_call(
    operation: Callable[[], T],
    *,
    exceptions: tuple[type[Exception], ...],
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[Exception, int, int], None] | None = None,
) -> T:
    for attempt in range(1, policy.attempts + 1):
        try:
            return operation()
        except exceptions as exc:
            if attempt >= policy.attempts:
                raise
            if on_retry is not None:
                on_retry(exc, attempt, policy.attempts)
            sleep(policy.delay_seconds)
    raise RuntimeError("Retry operation ended unexpectedly.")
