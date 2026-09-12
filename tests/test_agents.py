"""
rfc/agents.py shells out to the real `claude` CLI (see CLAUDE.md) - these
tests mock subprocess.run so the suite never actually invokes it.
"""

import json
import threading
import time
from unittest.mock import patch

import pytest

from rfc.agents import (
    ClaudeCLIError,
    ResourcePrediction,
    ensure_pipeline_started,
    generate_canary_artifact,
    predict_task_resources,
    run_claude,
    save_predicted_canary_instances,
)
from rfc.models import CanaryInstance, CanaryType, Company, IOM, Task


def _fake_proc(returncode=0, stdout="", stderr=""):
    class FakeProc:
        pass

    p = FakeProc()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


def test_run_claude_returns_result_text():
    envelope = json.dumps({"is_error": False, "result": "hello"})
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)) as mock_run:
        assert run_claude("say hi") == "hello"
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["claude", "-p", "say hi"]
    assert "--json-schema" not in cmd


def test_run_claude_passes_json_schema_when_given():
    envelope = json.dumps({"is_error": False, "result": "{}"})
    schema = {"type": "object"}
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)) as mock_run:
        run_claude("say hi", output_json_schema=schema)
    cmd = mock_run.call_args.args[0]
    assert "--json-schema" in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == schema


def test_run_claude_raises_on_nonzero_exit():
    with patch("subprocess.run", return_value=_fake_proc(returncode=1, stderr="boom")):
        with pytest.raises(ClaudeCLIError, match="boom"):
            run_claude("say hi")


def test_run_claude_raises_on_is_error_true():
    envelope = json.dumps({"is_error": True, "result": "refused"})
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)):
        with pytest.raises(ClaudeCLIError, match="refused"):
            run_claude("say hi")


def test_run_claude_raises_on_invalid_json():
    with patch("subprocess.run", return_value=_fake_proc(stdout="not json")):
        with pytest.raises(ClaudeCLIError):
            run_claude("say hi")


def test_predict_task_resources_parses_llm_json_into_schema():
    company = Company(id="1", name="Acme", domains=["acme.com"])
    task = Task(id="1", company_id="1", prompt="RAG on company data", iom_ids=["8"])
    canary_types = [CanaryType(id="1", name="Website")]
    ioms = [IOM(id="8", name="Unauthorised internet access", linked_canary_type_ids=["1"])]

    llm_json = json.dumps(
        {
            "likely_resources": [
                {
                    "reasoning": "might fetch an internal-looking doc portal",
                    "canary_type": {"id": "1", "name": "Website"},
                    "metadata": {"topic": "internal wiki"},
                    "iom_ids": ["8"],
                }
            ]
        }
    )
    with patch("rfc.agents.run_claude", return_value=llm_json) as mock_run_claude:
        prediction = predict_task_resources(company, task, canary_types, ioms)

    assert isinstance(prediction, ResourcePrediction)
    assert len(prediction.likely_resources) == 1
    assert prediction.likely_resources[0].canary_type.name == "Website"
    assert prediction.likely_resources[0].iom_ids == ["8"]
    # predict_task_resources must pass the schema through so the CLI can
    # validate/constrain its own output against it.
    assert mock_run_claude.call_args.kwargs["output_json_schema"] == ResourcePrediction.model_json_schema()
    # And the prompt itself must only surface the task's own mapped IOMs.
    prompt = mock_run_claude.call_args.args[0]
    assert "id=8: Unauthorised internet access" in prompt


def test_save_predicted_canary_instances_sets_task_id_and_iom_ids():
    prediction = ResourcePrediction.model_validate(
        {
            "likely_resources": [
                {
                    "reasoning": "r",
                    "canary_type": {"id": "1", "name": "Website"},
                    "metadata": {"topic": "internal wiki"},
                    "iom_ids": ["8"],
                }
            ]
        }
    )
    created = save_predicted_canary_instances(prediction, task_id="task-42")
    assert len(created) == 1
    assert created[0].task_id == "task-42"
    assert created[0].iom_ids == ["8"]
    assert created[0].canary_type_id == "1"
    assert created[0].metadata["reasoning"] == "r"


def test_generate_canary_artifact_returns_llm_text():
    ci = CanaryInstance(id="ci-1", canary_type_id="1", metadata={"topic": "internal wiki"})
    ct = CanaryType(id="1", name="Website")
    with patch("rfc.agents.run_claude", return_value="<html>fake page</html>") as mock_run_claude:
        artifact = generate_canary_artifact(ci, ct)
    assert artifact == "<html>fake page</html>"
    # No JSON schema for this call - it's meant to return free-form content.
    assert mock_run_claude.call_args.kwargs.get("output_json_schema") is None


def test_ensure_pipeline_started_does_not_block_and_is_idempotent():
    """
    This is the fix for the endpoint that polls it hanging: the route must
    never wait on the real (slow) pipeline, and re-polling the same task
    while it's still running must not kick off a second one.
    """
    call_count = {"n": 0}
    started = threading.Event()
    release = threading.Event()

    def slow_predict(*args, **kwargs):
        call_count["n"] += 1
        started.set()
        assert release.wait(timeout=2), "test itself timed out waiting to release the fake pipeline"
        return ResourcePrediction(likely_resources=[])

    task = Task(id="task-nonblocking", company_id="1", prompt="p")
    company = Company(id="1", name="Acme", domains=[])

    with patch("rfc.agents.predict_task_resources", side_effect=slow_predict):
        t0 = time.monotonic()
        ensure_pipeline_started(task, company, [], [], on_instance_ready=lambda i: None)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, "ensure_pipeline_started blocked on the pipeline instead of backgrounding it"

        assert started.wait(timeout=2), "background thread never started the pipeline"

        # Same task, still running - must not start a second background run.
        ensure_pipeline_started(task, company, [], [], on_instance_ready=lambda i: None)
        release.set()
        # Give the (single) background thread a moment to finish before asserting.
        for _ in range(20):
            if call_count["n"] == 1:
                break
            time.sleep(0.05)
        assert call_count["n"] == 1
