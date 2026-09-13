"""Exponential backoff helper used by Scheduler retries.

Complete - reference only, nothing to implement here.
"""

from __future__ import annotations


def compute_delay(
    attempt: int,
    base_delay: float = 1.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> float:
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    delay = base_delay * (multiplier ** (attempt - 1))
    return min(delay, max_delay)
