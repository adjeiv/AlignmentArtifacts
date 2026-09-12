"""
Structural tests against frontend/CONTRACT.md: every endpoint it documents
responds with the status code and fields the frontend actually reads.
This is not exhaustive - it's a floor to catch a route/field disappearing or
changing shape without CONTRACT.md (and this suite) being updated to match,
per CLAUDE.md.

Never calls the real `claude` CLI: backend.agents.classify_task_ioms and
.deploy_canary_instance are monkeypatched wherever a route depends on them.
"""

from fastapi.testclient import TestClient

import data
from backend.api import app
from backend.models import CanaryEvent, CanaryInstance

client = TestClient(app)

KNOWN_COMPANY_ID = "1"
KNOWN_TASK_ID = "1"


# --- Companies -------------------------------------------------------------


def test_list_companies_returns_managed_companies():
    res = client.get("/api/companies")
    assert res.status_code == 200
    companies = res.json()
    assert isinstance(companies, list)
    ids = {c["id"] for c in companies}
    assert KNOWN_COMPANY_ID in ids
    for company in companies:
        assert {"id", "name", "domains", "compliance_status"} <= company.keys()
        assert company["compliance_status"] in {
            "compliant",
            "at_risk",
            "non_compliant",
            "pending_review",
        }


def test_get_company_by_id():
    res = client.get(f"/api/companies/{KNOWN_COMPANY_ID}")
    assert res.status_code == 200
    assert res.json()["id"] == KNOWN_COMPANY_ID


def test_get_company_404_for_unknown_id():
    res = client.get("/api/companies/does-not-exist")
    assert res.status_code == 404


def test_company_compliance_status_is_computed_not_the_raw_mock_value():
    # data.py's seed value is "SOC2 compliant" - the API must never pass
    # that straight through (see CONTRACT.md's derivation rule).
    res = client.get(f"/api/companies/{KNOWN_COMPANY_ID}")
    assert res.json()["compliance_status"] != "SOC2 compliant"


# --- Tasks -------------------------------------------------------------


def test_list_company_tasks():
    res = client.get(f"/api/companies/{KNOWN_COMPANY_ID}/tasks")
    assert res.status_code == 200
    tasks = res.json()
    assert isinstance(tasks, list) and len(tasks) >= 1
    for task in tasks:
        assert {"id", "company_id", "prompt", "models", "constraints", "iom_ids"} <= task.keys()
        assert task["company_id"] == KNOWN_COMPANY_ID


def test_list_company_tasks_404_for_unknown_company():
    res = client.get("/api/companies/does-not-exist/tasks")
    assert res.status_code == 404


def test_get_task_by_id():
    res = client.get(f"/api/tasks/{KNOWN_TASK_ID}")
    assert res.status_code == 200
    assert res.json()["id"] == KNOWN_TASK_ID


def test_get_task_404_for_unknown_id():
    res = client.get("/api/tasks/does-not-exist")
    assert res.status_code == 404


# --- Task creation (classify_task_ioms / deploy_canary_instance mocked) ----


def test_create_task_maps_ioms_and_spawns_canaries(monkeypatch):
    monkeypatch.setattr("backend.api.classify_task_ioms", lambda task, ioms: ["8"])

    def fake_spawn(task, ioms, canary_types):
        return [
            CanaryInstance(
                id="spawned-test-ci",
                canary_type_id=canary_types[0].id,
                task_id=task.id,
                iom_ids=["8"],
            )
        ]

    monkeypatch.setattr("backend.api.spawn_canary_instances_for_task", fake_spawn)

    async def fake_deploy(instance, task, canary_types):
        instance.deployment_health = "active"

    monkeypatch.setattr("backend.api.deploy_canary_instance", fake_deploy)

    res = client.post(f"/api/companies/{KNOWN_COMPANY_ID}/tasks", json={"prompt": "a brand new task"})
    assert res.status_code == 201
    task = res.json()
    assert task["prompt"] == "a brand new task"
    assert task["company_id"] == KNOWN_COMPANY_ID
    assert task["iom_ids"] == ["8"]

    # Step 2 (spawning) is synchronous, so the spawned instance must already
    # be visible - both via this task's canary-instances list...
    instances_res = client.get(f"/api/tasks/{task['id']}/canary-instances")
    assert instances_res.status_code == 200
    ids = {i["id"] for i in instances_res.json()}
    assert "spawned-test-ci" in ids

    # ...and via the canary-instance detail/events routes.
    detail_res = client.get("/api/canary-instances/spawned-test-ci")
    assert detail_res.status_code == 200
    events_res = client.get("/api/canary-instances/spawned-test-ci/events")
    assert events_res.status_code == 200


def test_create_task_404_for_unknown_company(monkeypatch):
    res = client.post("/api/companies/does-not-exist/tasks", json={"prompt": "p"})
    assert res.status_code == 404


# --- Canary instances --------------------------------------------------


def test_list_task_canary_instances_shape():
    # create_task() is what normally populates this (see above) - appending
    # directly here exercises the route (a plain filter, no side effects) on
    # its own.
    data.canary_instances.append(
        CanaryInstance(
            id="test-ci-shape",
            canary_type_id=data.canary_types[0].id,
            task_id=KNOWN_TASK_ID,
            iom_ids=["8"],
        )
    )

    res = client.get(f"/api/tasks/{KNOWN_TASK_ID}/canary-instances")
    assert res.status_code == 200
    instances = res.json()
    instance = next(i for i in instances if i["id"] == "test-ci-shape")
    assert {
        "id",
        "canary_type_id",
        "metadata",
        "task_id",
        "iom_ids",
        "deployment_health",
        "triggered",
        "triggered_iom_id",
        "deployed_at",
        "last_heartbeat_at",
        "target_url",
    } <= instance.keys()
    assert instance["task_id"] == KNOWN_TASK_ID


def test_get_canary_instance_404_for_unknown_id():
    assert client.get("/api/canary-instances/does-not-exist").status_code == 404
    assert client.get("/api/canary-instances/does-not-exist/events").status_code == 404


def test_canary_instance_events_sorted_newest_first():
    data.canary_events.extend(
        [
            CanaryEvent(id="test-ce-1", canary_instance_id="test-ce-target", timestamp="2026-01-01T00:00:00Z", level="info", message="older"),
            CanaryEvent(id="test-ce-2", canary_instance_id="test-ce-target", timestamp="2026-06-01T00:00:00Z", level="info", message="newer"),
        ]
    )

    res = client.get("/api/canary-instances/test-ce-target/events")
    assert res.status_code == 404  # no such CanaryInstance exists

    # The 404 above is expected (events are keyed off a real instance id per
    # the route's own 404 check) - so seed a matching instance too.
    data.canary_instances.append(
        CanaryInstance(id="test-ce-target", canary_type_id=data.canary_types[0].id)
    )
    res = client.get("/api/canary-instances/test-ce-target/events")
    assert res.status_code == 200
    timestamps = [e["timestamp"] for e in res.json()]
    assert timestamps == ["2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z"]


# --- Reference data ------------------------------------------------------


def test_list_ioms():
    res = client.get("/api/ioms")
    assert res.status_code == 200
    ioms = res.json()
    assert isinstance(ioms, list) and len(ioms) >= 1
    for iom in ioms:
        assert {"id", "name", "linked_canary_type_ids"} <= iom.keys()


def test_list_canary_types():
    res = client.get("/api/canary-types")
    assert res.status_code == 200
    canary_types = res.json()
    assert isinstance(canary_types, list) and len(canary_types) >= 1
    for canary_type in canary_types:
        assert {"id", "name"} <= canary_type.keys()
