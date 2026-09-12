"""
FastAPI app serving the endpoints described in frontend/CONTRACT.md, backed
by the in-memory data in data.py and shaped per frontend/src/types/contract.ts
and backend/models.py.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

import data
from backend.models import CanaryEvent, CanaryInstance, ComplianceStatus, LogLevel
from backend.agents import classify_task_ioms, deploy_canary_instance, spawn_canary_instances_for_task

app = FastAPI(title="Alignment Artifacts API")


class CreateTaskRequest(BaseModel):
    prompt: str


# --- Helpers -------------------------------------------------------------


def _company_or_404(company_id: str) -> data.Company:
    for company in data.companies:
        if company.id == company_id:
            return company
    raise HTTPException(status_code=404, detail=f"Company {company_id!r} not found")


def _task_or_404(task_id: str) -> data.Task:
    for task in data.tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")


def _canary_instance_or_404(canary_instance_id: str) -> CanaryInstance:
    for instance in data.canary_instances:
        if instance.id == canary_instance_id:
            return instance
    raise HTTPException(
        status_code=404, detail=f"CanaryInstance {canary_instance_id!r} not found"
    )


def _compliance_status_for(company: data.Company) -> str:
    """Implements the derivation rule in frontend/CONTRACT.md rather than
    trusting Company.compliance_status, which is currently just a mock
    string ("SOC2 compliant" in data.py) that predates this rule."""
    company_tasks = [t for t in data.tasks if t.company_id == company.id]
    task_ids = {t.id for t in company_tasks}
    mapped_iom_ids = {iom_id for t in company_tasks for iom_id in t.iom_ids}

    company_instances = [ci for ci in data.canary_instances if ci.task_id in task_ids]

    triggered = [ci for ci in company_instances if ci.triggered]
    if triggered:
        # TODO: CONTRACT.md distinguishes non_compliant ("confirmed/open")
        # from at_risk ("pending investigation"), but no field anywhere
        # models a finding's investigation status yet. Defaulting to the
        # more conservative non_compliant until backend adds one (e.g.
        # CanaryInstance.finding_status).
        return ComplianceStatus.NON_COMPLIANT.value

    covered_iom_ids = {iom_id for ci in company_instances for iom_id in ci.iom_ids}
    if not mapped_iom_ids.issubset(covered_iom_ids):
        return ComplianceStatus.PENDING_REVIEW.value

    return ComplianceStatus.COMPLIANT.value


def _with_computed_compliance(company: data.Company) -> data.Company:
    return data.Company(
        id=company.id,
        name=company.name,
        domains=company.domains,
        compliance_status=_compliance_status_for(company),
    )


# --- Companies ---------------------------------------------------------
# TODO: GET /api/companies is scoped by Dashboard.managed_company_ids, but
# there's no auth yet (CONTRACT.md open question 1) to say *which* Dashboard
# is asking, and data.py only ever seeds one. For now this always filters to
# that single seeded Dashboard; once auth exists, resolve the caller's
# Dashboard from it instead of hardcoding data.dashboard here.


@app.get("/api/companies")
def list_companies() -> list[data.Company]:
    managed_ids = set(data.dashboard.managed_company_ids)
    return [
        _with_computed_compliance(c) for c in data.companies if c.id in managed_ids
    ]


@app.get("/api/companies/{company_id}")
def get_company(company_id: str) -> data.Company:
    return _with_computed_compliance(_company_or_404(company_id))


@app.get("/api/companies/{company_id}/tasks")
def list_company_tasks(company_id: str) -> list[data.Task]:
    _company_or_404(company_id)
    return [t for t in data.tasks if t.company_id == company_id]


async def _deploy_canaries(task: data.Task, instances: list[CanaryInstance]) -> None:
    """Step 3 of CONTRACT.md's task creation pipeline, run as a background
    task so POST /api/companies/{company_id}/tasks doesn't block on it - this
    is the only part that makes Claude calls, so it's the only part backgrounded."""
    await asyncio.gather(
        *(deploy_canary_instance(ci, task, data.canary_types) for ci in instances)
    )


@app.post("/api/companies/{company_id}/tasks", status_code=201)
def create_task(
    company_id: str, body: CreateTaskRequest, background_tasks: BackgroundTasks
) -> data.Task:
    _company_or_404(company_id)

    task = data.Task(id=str(uuid.uuid4()), company_id=company_id, prompt=body.prompt)
    # Step 1 (the compliance-mapping step) runs synchronously - the frontend
    # gets the task back with its IOM mapping already assigned.
    task.iom_ids = classify_task_ioms(task, data.ioms)
    data.tasks.append(task)

    # Step 2 (spawning) also runs synchronously - it's pure computation, no
    # API calls - so GET .../canary-instances is guaranteed non-empty by the
    # time the caller has this response, and an empty list there always means
    # "genuinely no canary coverage", never "hasn't been spawned yet".
    instances = spawn_canary_instances_for_task(task, data.ioms, data.canary_types)
    data.canary_instances.extend(instances)

    background_tasks.add_task(_deploy_canaries, task, instances)
    return task


# TODO (nice-to-have per CONTRACT.md, not blocking the PoC):
# GET /api/companies/{company_id}/summary - precomputed task/canary counts.
# No response shape has been defined for it yet.


# --- Tasks ---------------------------------------------------------------


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> data.Task:
    return _task_or_404(task_id)


@app.get("/api/tasks/{task_id}/canary-instances")
def list_task_canary_instances(task_id: str) -> list[CanaryInstance]:
    # Never blocks: create_task() already spawned every CanaryInstance for
    # this task synchronously (only their deploy - the slow, real `claude`
    # CLI part - is backgrounded), so this is just a filter. An empty list
    # here always means "genuinely no canary coverage", never "hasn't been
    # generated yet" (see frontend/CONTRACT.md's task-creation-pipeline
    # section).
    _task_or_404(task_id)
    return [ci for ci in data.canary_instances if ci.task_id == task_id]


# --- Canary instances ------------------------------------------------------


@app.get("/api/canary-instances/{canary_instance_id}")
def get_canary_instance(canary_instance_id: str) -> CanaryInstance:
    return _canary_instance_or_404(canary_instance_id)


@app.get("/api/canary-instances/{canary_instance_id}/events")
def list_canary_instance_events(canary_instance_id: str) -> list[data.CanaryEvent]:
    _canary_instance_or_404(canary_instance_id)
    events = [
        e for e in data.canary_events if e.canary_instance_id == canary_instance_id
    ]
    return sorted(events, key=lambda e: e.timestamp, reverse=True)


@app.post("/api/canary-instances/{canary_instance_id}/trigger/{iom_id}")
def trigger_canary_instance(canary_instance_id: str, iom_id: str) -> CanaryInstance:
    """Called by log-monitor/monitor.py when a request matches one of this
    instance's registered endpoint regexes (see backend/agents.py's
    _register_endpoints). Flips triggered/triggered_iom_id and logs a TRIGGER
    CanaryEvent - Company.compliance_status is computed live from these on
    every read (_compliance_status_for below), so nothing else needs to be
    told about the hit."""
    instance = _canary_instance_or_404(canary_instance_id)
    if iom_id not in instance.iom_ids:
        raise HTTPException(
            status_code=400,
            detail=f"IOM {iom_id!r} is not covered by canary instance {canary_instance_id!r}",
        )

    now = datetime.now(timezone.utc).isoformat()
    instance.triggered = True
    instance.triggered_iom_id = iom_id
    instance.last_heartbeat_at = now

    data.canary_events.append(
        CanaryEvent(
            id=str(uuid.uuid4()),
            canary_instance_id=instance.id,
            timestamp=now,
            level=LogLevel.TRIGGER.value,
            message=f"Canary endpoint hit - IOM {iom_id!r} detected",
            iom_id=iom_id,
        )
    )
    return instance


# --- Reference data --------------------------------------------------------


@app.get("/api/ioms")
def list_ioms() -> list[data.IOM]:
    return data.ioms


@app.get("/api/canary-types")
def list_canary_types() -> list[data.CanaryType]:
    return data.canary_types
