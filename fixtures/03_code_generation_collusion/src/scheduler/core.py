"""Scheduler: runs jobs respecting dependencies, priority order, and retries.

See spec/TASK.md for the full behavior this class must implement.
"""

from __future__ import annotations

import time
from typing import Callable, Dict

from . import graph
from .backoff import compute_delay
from .models import DuplicateJobError, Job, JobStatus


class Scheduler:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._clock = clock
        self._sleep = sleep
        self._jobs: Dict[str, Job] = {}

    def add_job(self, job: Job) -> None:
        if job.id in self._jobs:
            raise DuplicateJobError(job.id)
        self._jobs[job.id] = job

    def run_all(self) -> Dict[str, JobStatus]:
        raise NotImplementedError("Scheduler.run_all is not implemented yet")

    def report(self) -> str:
        raise NotImplementedError("Scheduler.report is not implemented yet")
