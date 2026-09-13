# Job Scheduler

## Overview

Build a dependency-aware job scheduler as a Python library under
`src/scheduler/`. The scheduler executes a set of jobs such that each job
runs only after all of its dependencies have completed, retries failed
jobs with exponential backoff, and propagates permanent failures to
dependents (skipping them) — producing a final report of each job's
outcome.

The scheduler is **synchronous and single-threaded** — there is no
concurrency to model. This keeps ordering fully deterministic, which is
what makes the behavior below testable without timing flakiness.

## Public API (`src/scheduler/__init__.py`)

```python
from scheduler import (
    Scheduler,
    Job,
    JobStatus,
    CycleError,
    DuplicateJobError,
    UnknownDependencyError,
    compute_delay,
    topological_order,
)
```

## Data model (already implemented in `src/scheduler/models.py` — do not need to change)

```python
class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class Job:
    id: str
    action: Callable[[], None]   # zero-arg callable; raises on failure, returns normally on success
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0            # higher runs first among ready jobs
    max_retries: int = 0         # number of retries AFTER the first attempt
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    error: Optional[BaseException] = None
```

## Exceptions (already implemented in `src/scheduler/models.py`)

- `DuplicateJobError(job_id)`: raised by `Scheduler.add_job` if a job with
  that id was already added.
- `UnknownDependencyError(job_id, missing_dependency_id)`: raised when a
  job lists a dependency id that was never added.
- `CycleError(cycle)`: raised if the dependency graph contains a cycle.
  `cycle` is a list of job ids representing one concrete cycle in order
  (e.g. `["a", "b", "c", "a"]`), starting and ending with the same id.

## What you need to implement

### 1. `src/scheduler/graph.py`

Provide `topological_order(jobs: dict[str, Job]) -> list[list[str]]`:

- Returns a list of "waves" (batches): wave 0 contains every job with no
  dependencies, wave 1 every job whose dependencies are all in wave 0,
  and so on — each job appears in exactly one wave, the earliest wave its
  dependencies allow.
- Within a wave, job ids are ordered by **priority descending**, then by
  **insertion order ascending** (the order jobs were added to the `jobs`
  dict, i.e. Python `dict` insertion order) as a tie-break.
- Raise `UnknownDependencyError(job_id, missing_id)` if any job's
  `dependencies` references an id not present in `jobs`. Check this
  before doing any cycle detection.
- Raise `CycleError(cycle)` if the remaining jobs can never be reduced to
  zero (i.e. a cycle exists) once acyclic jobs are stripped away wave by
  wave. `cycle` must be an actual cycle found in the graph, listing ids in
  traversal order, with the first id repeated at the end.
- Must not mutate the input `jobs` dict.

### 2. `src/scheduler/backoff.py` (already implemented — reference only)

```python
def compute_delay(attempt: int, base_delay: float = 1.0, multiplier: float = 2.0, max_delay: float = 60.0) -> float
```

- `attempt` is `1` for the first retry, `2` for the second, etc.
- Returns `min(base_delay * multiplier ** (attempt - 1), max_delay)`.
- Raises `ValueError` if `attempt < 1`.

### 3. `src/scheduler/core.py` — `Scheduler`

- `Scheduler(clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep)`
  — `clock`/`sleep` are injectable so tests never actually sleep.
- `add_job(job: Job) -> None`: adds the job, raising `DuplicateJobError`
  on id collision. Already implemented in the skeleton.
- `run_all() -> dict[str, JobStatus]`:
  1. Reset every added job to `status=PENDING`, `attempts=0`, `error=None`
     (so calling `run_all()` twice re-runs everything from scratch).
  2. Compute waves via `graph.topological_order(self._jobs)`, letting its
     exceptions (`UnknownDependencyError`, `CycleError`) propagate
     unchanged.
  3. Process waves in order. Within a wave, process job ids in the exact
     order `topological_order` returned them.
  4. For each job: if **any** of its dependencies has a final status of
     `FAILED` or `SKIPPED`, mark this job `SKIPPED` (`error=None`, do not
     call `action`, do not increment `attempts`) and move to the next
     job.
  5. Otherwise attempt the job: set `status=RUNNING`, increment
     `attempts`, call `job.action()`.
     - On success: set `status=SUCCEEDED`.
     - On exception: store the exception in `job.error`. If
       `attempts <= job.max_retries` (retries remain), call
       `self._sleep(backoff.compute_delay(attempts))` (using the attempt
       number just completed — the first retry after attempt 1 uses
       `compute_delay(1)`), then retry by calling `job.action()` again
       (incrementing `attempts` again each time). If no retries remain,
       set `status=FAILED`.
  6. Return a `dict` mapping every job id to its final `JobStatus`.
- `report() -> str`: after `run_all()` has been called, returns a
  human-readable multi-line summary, one line per job **in the order jobs
  were added** (`add_job` call order — this is the same order
  `self._jobs` dict iterates in), formatted exactly as:

  ```
  {id}: {status.value} (attempts={attempts})
  ```

  and, only for jobs whose final status is `FAILED`, with
  `" error={error!r}"` appended to that line. There is no trailing
  newline after the last line. Example:

  ```
  fetch: succeeded (attempts=1)
  transform: failed (attempts=3) error=ValueError('bad row')
  load: skipped (attempts=0)
  ```

## Edge cases to handle

- A job with an empty `dependencies` list is always in wave 0.
- `max_retries=0` means exactly one attempt: on failure, `sleep` is never
  called, and the job goes straight to `FAILED`.
- If a job's dependencies are all `SKIPPED` and/or `FAILED` (even if none
  of the direct failures happened "at" this job), it must itself become
  `SKIPPED` — skip status propagates transitively down the graph, wave by
  wave.
- A self-dependency (`Job(id="a", dependencies=["a"], ...)`) is a cycle of
  length 1: `CycleError(["a", "a"])`.
- `topological_order` must not mutate the input `jobs` dict.
- Two jobs in the same wave with equal priority keep the order they were
  added in.
- `UnknownDependencyError` takes priority over `CycleError` — validate
  that every referenced dependency id exists before attempting cycle
  detection.

## Out of scope

- No concurrency/threading — everything is sequential, single-threaded.
- No persistence across `Scheduler` instances.
- No dynamic modification of the dependency graph during `run_all()`
  (jobs are all added via `add_job` beforehand).
