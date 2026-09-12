"""
backend/agents.py shells out to the real `claude` CLI (see CLAUDE.md) - these
tests mock subprocess.run (or run_claude itself) so the suite never actually
invokes it.
"""

import asyncio
import json
from unittest.mock import patch

import pytest

from backend.agents import (
    CANARY_TYPE_HANDLERS,
    ClaudeCLIError,
    IomMapping,
    classify_task_ioms,
    deploy_canary_instance,
    get_canary_type_handler,
    run_claude,
    spawn_canary_instances_for_task,
    valid_canary_type_ids,
)
from backend.models import CanaryInstance, CanaryType, IOM, Task


def _fake_proc(returncode=0, stdout="", stderr=""):
    class FakeProc:
        pass

    p = FakeProc()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


# --- run_claude ------------------------------------------------------------


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


# --- classify_task_ioms -----------------------------------------------------


def test_classify_task_ioms_filters_ids_outside_the_catalog():
    task = Task(id="1", company_id="1", prompt="RAG on company data")
    ioms = [IOM(id="8", name="Unauthorised internet access", linked_canary_type_ids=["1"])]

    llm_json = IomMapping(iom_ids=["8", "not-a-real-id"]).model_dump_json()
    with patch("backend.agents.run_claude", return_value=llm_json) as mock_run_claude:
        result = classify_task_ioms(task, ioms)

    # The model echoed an id outside the catalog it was given - must be dropped.
    assert result == ["8"]
    assert mock_run_claude.call_args.kwargs["output_json_schema"] == IomMapping.model_json_schema()


# --- spawn_canary_instances_for_task / valid_canary_type_ids ---------------


def test_valid_canary_type_ids_dedupes_and_drops_unknown_types():
    iom = IOM(id="3", name="x", linked_canary_type_ids=["1", "1", "2", "unknown"])
    canary_types = [CanaryType(id="1", name="A"), CanaryType(id="2", name="B")]
    assert valid_canary_type_ids(iom, canary_types) == ["1", "2"]


def test_spawn_canary_instances_for_task_one_per_iom_canary_type_pair():
    task = Task(id="1", company_id="1", prompt="p", iom_ids=["3", "6"])
    ioms = [
        IOM(id="3", name="x", linked_canary_type_ids=["1", "2"]),
        IOM(id="6", name="gap", linked_canary_type_ids=[]),  # no linked type -> no canary
    ]
    canary_types = [CanaryType(id="1", name="A"), CanaryType(id="2", name="B")]

    created = spawn_canary_instances_for_task(task, ioms, canary_types)

    assert len(created) == 2
    assert {(c.canary_type_id, tuple(c.iom_ids)) for c in created} == {("1", ("3",)), ("2", ("3",))}
    for c in created:
        assert c.task_id == "1"
        assert c.deployment_health == "pending"


def test_spawn_canary_instances_for_task_skips_unknown_iom_id():
    task = Task(id="1", company_id="1", prompt="p", iom_ids=["does-not-exist"])
    created = spawn_canary_instances_for_task(task, ioms=[], canary_types=[])
    assert created == []


# --- deploy_canary_instance / deploy handlers -------------------------------


def test_get_canary_type_handler_routes_message_board_to_its_own_handler():
    assert get_canary_type_handler("4") is CANARY_TYPE_HANDLERS["4"]
    # Anything else falls back to the generic default.
    assert get_canary_type_handler("1") is not CANARY_TYPE_HANDLERS["4"]


def test_deploy_canary_instance_default_handler_activates_and_sets_target_url():
    instance = CanaryInstance(id="ci-1", canary_type_id="1", task_id="1", iom_ids=["8"])
    task = Task(id="1", company_id="1", prompt="RAG on company data")
    canary_types = [CanaryType(id="1", name="Impersonation server")]

    with patch("backend.agents.run_claude", return_value="fake artifact") as mock_run_claude:
        asyncio.run(deploy_canary_instance(instance, task, canary_types))

    mock_run_claude.assert_called_once()
    assert instance.deployment_health == "active"
    assert instance.metadata["artifact"] == "fake artifact"
    assert instance.target_url is not None
    assert instance.deployed_at is not None
