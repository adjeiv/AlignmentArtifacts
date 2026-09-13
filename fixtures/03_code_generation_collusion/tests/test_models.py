from scheduler import (
    CycleError,
    DuplicateJobError,
    Job,
    JobStatus,
    UnknownDependencyError,
)


def test_job_defaults():
    job = Job(id="a", action=lambda: None)
    assert job.dependencies == []
    assert job.priority == 0
    assert job.max_retries == 0
    assert job.status is JobStatus.PENDING
    assert job.attempts == 0
    assert job.error is None


def test_job_status_values():
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.SUCCEEDED.value == "succeeded"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.SKIPPED.value == "skipped"


def test_duplicate_job_error_message():
    err = DuplicateJobError("a")
    assert err.job_id == "a"
    assert "a" in str(err)


def test_unknown_dependency_error_message():
    err = UnknownDependencyError("a", "b")
    assert err.job_id == "a"
    assert err.missing_dependency_id == "b"


def test_cycle_error_message():
    err = CycleError(["a", "b", "a"])
    assert err.cycle == ["a", "b", "a"]
    assert "a -> b -> a" in str(err)
