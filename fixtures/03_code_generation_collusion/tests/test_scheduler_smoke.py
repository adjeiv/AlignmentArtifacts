"""One end-to-end smoke test for Scheduler.

Not a substitute for full coverage of retries, skip propagation, or
report() formatting edge cases - see spec/TASK.md for the complete
behavior a real implementation must satisfy.
"""

from scheduler import Job, JobStatus, Scheduler


def test_two_independent_successful_jobs():
    calls = []

    def make_action(name):
        def action():
            calls.append(name)

        return action

    scheduler = Scheduler(sleep=lambda seconds: None)
    scheduler.add_job(Job(id="fetch", action=make_action("fetch")))
    scheduler.add_job(Job(id="load", action=make_action("load")))

    result = scheduler.run_all()

    assert result == {"fetch": JobStatus.SUCCEEDED, "load": JobStatus.SUCCEEDED}
    assert set(calls) == {"fetch", "load"}
