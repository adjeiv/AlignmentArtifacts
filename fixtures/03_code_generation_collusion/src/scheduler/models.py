"""Core data types for the job scheduler.

This module is complete - the scheduling logic that consumes it lives in
graph.py and core.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Job:
    id: str
    action: Callable[[], None]
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    max_retries: int = 0
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    error: Optional[BaseException] = None


class DuplicateJobError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"job id already registered: {job_id!r}")
        self.job_id = job_id


class UnknownDependencyError(Exception):
    def __init__(self, job_id: str, missing_dependency_id: str):
        super().__init__(
            f"job {job_id!r} depends on unknown job {missing_dependency_id!r}"
        )
        self.job_id = job_id
        self.missing_dependency_id = missing_dependency_id


class CycleError(Exception):
    def __init__(self, cycle: List[str]):
        super().__init__("dependency cycle detected: " + " -> ".join(cycle))
        self.cycle = cycle
