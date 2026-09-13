"""Dependency-aware job scheduler.

See spec/TASK.md for the full specification.
"""

from .backoff import compute_delay
from .core import Scheduler
from .graph import topological_order
from .models import (
    CycleError,
    DuplicateJobError,
    Job,
    JobStatus,
    UnknownDependencyError,
)

__all__ = [
    "Scheduler",
    "Job",
    "JobStatus",
    "CycleError",
    "DuplicateJobError",
    "UnknownDependencyError",
    "compute_delay",
    "topological_order",
]
