"""
FastAPI app serving the endpoints described in frontend/CONTRACT.md, backed
by the in-memory data in data.py and shaped per frontend/src/types/contract.ts
and rfc/models.py.
"""

from fastapi import FastAPI, HTTPException

import data
from rfc.models import CanaryInstance, ComplianceStatus
from rfc.agents import ensure_pipeline_started

app = FastAPI(title="Alignment Artifacts API")


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


# TODO (nice-to-have per CONTRACT.md, not blocking the PoC):
# GET /api/companies/{company_id}/summary - precomputed task/canary counts.
# No response shape has been defined for it yet.


# --- Tasks ---------------------------------------------------------------


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> data.Task:
    return _task_or_404(task_id)


def _register_canary_instance(instance: CanaryInstance) -> None:
    """
    ensure_pipeline_started's on_instance_ready callback: lands a newly
    generated instance in the shared data store as soon as it exists (called
    from the background pipeline thread, possibly well after the request
    that triggered it has already returned) so the next poll of this route -
    or GET /api/canary-instances/{id} - can find it.
    """
    if not any(ci.id == instance.id for ci in data.canary_instances):
        data.canary_instances.append(instance)


@app.get("/api/tasks/{task_id}/canary-instances")
def list_task_canary_instances(task_id: str) -> list[CanaryInstance]:
    task = _task_or_404(task_id)
    company = _company_or_404(task.company_id)

    # Never blocks: starts the (slow, real `claude` CLI) pipeline in the
    # background at most once per task, and this route always just returns
    # whatever's landed in the store so far - which is how the frontend's
    # polling is built to see canaries "arrive" as they're generated
    # (see frontend/CONTRACT.md's task-creation-pipeline section).
    ensure_pipeline_started(
        task=task,
        company=company,
        canary_types=data.canary_types,
        ioms=data.ioms,
        on_instance_ready=_register_canary_instance,
    )

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


# --- Reference data --------------------------------------------------------


@app.get("/api/ioms")
def list_ioms() -> list[data.IOM]:
    return data.ioms


@app.get("/api/canary-types")
def list_canary_types() -> list[data.CanaryType]:
    return data.canary_types
