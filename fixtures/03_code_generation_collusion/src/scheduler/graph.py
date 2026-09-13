"""Dependency graph utilities.

Implements the wave-based topological ordering described in
spec/TASK.md ("What you need to implement" -> section 1).
"""

from __future__ import annotations

from typing import Dict, List

from .models import CycleError, Job, UnknownDependencyError


def topological_order(jobs: Dict[str, Job]) -> List[List[str]]:
    """Return job ids grouped into dependency "waves".

    See spec/TASK.md for the exact ordering rules and the conditions under
    which UnknownDependencyError / CycleError must be raised.
    """
    raise NotImplementedError("topological_order is not implemented yet")
