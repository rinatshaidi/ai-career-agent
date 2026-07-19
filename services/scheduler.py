from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Event
from typing import Callable


logger = logging.getLogger("jobmonitor.scheduler")


@dataclass(slots=True)
class IntervalScheduler:
    task: Callable[[], object]
    interval_seconds: int
    stop_event: Event = field(default_factory=Event)
    monotonic: Callable[[], float] = field(default=time.monotonic, repr=False)

    def __post_init__(self) -> None:
        if self.interval_seconds < 1:
            raise ValueError("Scheduler interval must be positive.")

    def run_once(self) -> object:
        return self.task()

    def run_forever(self) -> None:
        logger.info("Scheduler started interval_seconds=%s", self.interval_seconds)
        while not self.stop_event.is_set():
            started_at = self.monotonic()
            try:
                self.task()
            except Exception:
                logger.exception("Scheduled cycle failed; the scheduler will continue.")
            elapsed = self.monotonic() - started_at
            wait_seconds = max(0.0, self.interval_seconds - elapsed)
            if self.stop_event.wait(wait_seconds):
                break
        logger.info("Scheduler stopped.")

    def stop(self) -> None:
        self.stop_event.set()
