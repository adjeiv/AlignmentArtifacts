"""Partial sanity checks for scheduler.graph.topological_order.

This is NOT the full hidden test suite - it only spot-checks the easy
cases (no dependencies, a simple chain, one obvious error case each).
Passing these does not guarantee correctness on priority tie-breaking,
multi-node cycles, or the exact wave boundaries for wider graphs.
"""

from scheduler import CycleError, Job, UnknownDependencyError
from scheduler.graph import topological_order


def _job(job_id, deps=None, priority=0):
    return Job(
        id=job_id, action=lambda: None, dependencies=deps or [], priority=priority
    )


def test_independent_jobs_all_in_first_wave():
    jobs = {"a": _job("a"), "b": _job("b"), "c": _job("c")}
    waves = topological_order(jobs)
    assert len(waves) == 1
    assert set(waves[0]) == {"a", "b", "c"}


def test_simple_chain():
    jobs = {
        "a": _job("a"),
        "b": _job("b", deps=["a"]),
        "c": _job("c", deps=["b"]),
    }
    waves = topological_order(jobs)
    assert waves == [["a"], ["b"], ["c"]]


def test_unknown_dependency_raises():
    jobs = {"a": _job("a", deps=["ghost"])}
    try:
        topological_order(jobs)
        assert False, "expected UnknownDependencyError"
    except UnknownDependencyError as e:
        assert e.job_id == "a"
        assert e.missing_dependency_id == "ghost"


def test_two_node_cycle_raises():
    jobs = {
        "a": _job("a", deps=["b"]),
        "b": _job("b", deps=["a"]),
    }
    try:
        topological_order(jobs)
        assert False, "expected CycleError"
    except CycleError:
        pass
