# Frontend <-> Backend consumer contract

Status: **draft, for review**. This is what the frontend needs from the API;
please push back on anything that doesn't fit the backend's plans.

## Data model

The frontend's fields have been folded into `backend/models.py` directly
(there's no longer a separate `rfc/frontend_models.py` - that file's proposed
extensions are now the real `Task` and `CanaryInstance` dataclasses):

- `Task.iom_ids: list[str]` - the IOMs this task has been mapped to. Drives
  the mind-map view's branches.
- `CanaryInstance.task_id`, `.iom_ids`, `.deployment_health`, `.triggered`,
  `.triggered_iom_id`, `.deployed_at`, `.last_heartbeat_at`, `.target_url`.
  A canary instance is deployed against one task and covers detection for a
  subset of that task's `iom_ids`.
- `CanaryInstance.name` - a short (2-3 word) human-readable UI label, e.g.
  "Fake Answer Key", set at spawn time. Distinct from `CanaryType.name`
  (the category, e.g. "Fake answers canary") since one task can spawn
  several instances of the same type for different IOMs - use this for the
  per-instance label, the type's own name/icon for the category.
- `CanaryEvent` dataclass - the log/trigger stream for one canary
  instance. A `level == "trigger"` event is what flips
  `CanaryInstance.triggered` and names the detected `iom_id`.
- `ComplianceStatus`, `DeploymentHealth`, `LogLevel` enums - plain `str`
  enums so they serialize as normal strings.
- `Company.compliance_status` is expected to hold one of `ComplianceStatus`'s
  values, computed from whether any canary covering the company's tasks has
  triggered - not a certification label like the old mock value ("SOC2
  compliant"). The API computes this per-request rather than trusting the
  stored field (see `backend/api.py`).

`frontend/src/types/contract.ts` mirrors `backend/models.py` 1:1 for the
frontend; the Python dataclasses are canonical.

## Derivation rule (frontend assumes this; flag if backend disagrees)

`Company.compliance_status`:
- `non_compliant` - a canary has triggered and the finding is confirmed/open
- `at_risk` - a canary has triggered and is pending investigation
- `compliant` - all mapped IOMs have canary coverage and nothing has triggered
- `pending_review` - one or more mapped IOMs have no canary coverage yet
  (e.g. no `CanaryType` linked, or no `CanaryInstance` deployed)

## Endpoints the frontend needs

All responses JSON, all lists possibly empty, no pagination in this PoC.

| Method | Path | Returns | Used by |
|---|---|---|---|
| GET | `/api/companies` | `Company[]` | Company dashboard (view 1) |
| GET | `/api/companies/{company_id}` | `Company` | Company detail header |
| GET | `/api/companies/{company_id}/tasks` | `Task[]` | Task list for a company |
| POST | `/api/companies/{company_id}/tasks` | `Task` (201) | "New task" composer (view 2) |
| GET | `/api/tasks/{task_id}` | `Task` | Mind-map center node |
| GET | `/api/tasks/{task_id}/canary-instances` | `CanaryInstance[]` | Mind-map branches |
| GET | `/api/canary-instances/{canary_instance_id}` | `CanaryInstance` | Canary status view (view 3) |
| GET | `/api/canary-instances/{canary_instance_id}/events` | `CanaryEvent[]` (newest first) | Canary status view logs |
| POST | `/api/canary-instances/{canary_instance_id}/trigger/{iom_id}` | `CanaryInstance` | Not called by the frontend - called by `log-monitor/` when a request matches a canary's registered endpoint regex. `iom_id` must be one of the instance's `iom_ids` (400 otherwise). Sets `triggered`/`triggered_iom_id`, appends a `level: "trigger"` `CanaryEvent`; `Company.compliance_status` picks this up on its next fetch, no separate step needed. |
| GET | `/api/ioms` | `IOM[]` | IOM leaf labels + coverage lookup (rarely changes; fine to fetch once and cache) |
| GET | `/api/canary-types` | `CanaryType[]` | Canary node labels/icons (rarely changes) |

Nice-to-have, not blocking the PoC:
- `GET /api/companies/{company_id}/summary` - precomputed counts (task
  count, canary count by health, triggered count) so the dashboard list
  doesn't need to fan out N+1 requests per company.

## Task creation pipeline

`POST /api/companies/{company_id}/tasks` (`{"prompt": string}`) implements
this as, synchronously before responding (both fast - no `claude` CLI call
in step 2, and only a small structured one in step 1):
1. `classify_task_ioms` - assign the `Task.iom_ids` (the compliance-mapping
   step).
2. `spawn_canary_instances_for_task` - one `CanaryInstance`
   (`deployment_health: "pending"`) per (mapped IOM, linked canary type)
   pair - an IOM linked to several canary types gets one of each; an IOM
   with no linked canary type stays an uncovered gap, same as the seed
   data's IOM "6" and "7". So the response already has `iom_ids` filled in,
   and `GET .../canary-instances` is guaranteed non-empty by the time the
   caller has it (an empty list there always means "genuinely no
   coverage", never "hasn't been generated yet").

Then, backgrounded (FastAPI `BackgroundTasks`, run concurrently via
`asyncio.gather` - this is the only part that calls `claude`, so it's the
only part that doesn't block the response):
3. `deploy_canary_instance` per spawned instance - generates its artifact
   and flips it to `deployment_health: "active"` (see
   `backend/agents.py`'s `CANARY_TYPE_HANDLERS` - message board canaries get
   a real deploy onto the `static-site/` container; everything else is
   `deploy_noop`, which never produces `"degraded"`/`"offline"` yet).

The frontend polls `GET /tasks/{task_id}/canary-instances` every second
after creating a task (and while viewing any task with `pending` instances)
until every returned instance has left `"pending"`, then stops.
`frontend/src/api/mockPipeline.ts` is a mock stand-in for all of this (fake
IOM mapping, staggered generation, delayed deploy) so the create-task UI
has something to poll against in mock mode.

## Open questions for backend

1. Auth: none assumed yet for the PoC - is there a token/session to plumb
   through later?
2. `CanaryInstance.metadata` now carries `"artifact"` (the generated content
   placed at the canary) - is the frontend meant to render/link to it
   anywhere (e.g. the canary status view), or is it backend/deploy-internal?
3. `deploy_canary_instance` always succeeds (after a simulated delay) - is a
   failure path (`"degraded"`/`"offline"`) planned, since the frontend
   already has tones for both?
