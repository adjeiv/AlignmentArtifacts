# Frontend <-> Backend consumer contract

Status: **draft, for review**. This is what the frontend needs from the API;
please push back on anything that doesn't fit the backend's plans.

## Data model

`rfc/models.py` is untouched. The frontend's proposed additions live in
**`rfc/frontend_models.py`**, which subclasses `Task` and `CanaryInstance`
from `models.py` and adds fields (all with defaults, so nothing existing
breaks) rather than editing the shared file directly - review it there and
fold whatever you're happy with back into `models.py` when it's settled:

- `Task.iom_ids: list[str]` - the IOMs this task has been mapped to. Drives
  the mind-map view's branches.
- `CanaryInstance.task_id`, `.iom_ids`, `.deployment_health`, `.triggered`,
  `.triggered_iom_id`, `.deployed_at`, `.last_heartbeat_at`, `.target_url`.
  A canary instance is deployed against one task and covers detection for a
  subset of that task's `iom_ids`.
- New `CanaryEvent` dataclass - the log/trigger stream for one canary
  instance. A `level == "trigger"` event is what flips
  `CanaryInstance.triggered` and names the detected `iom_id`.
- New enums (`ComplianceStatus`, `DeploymentHealth`, `LogLevel`) - plain
  `str` enums so they serialize as normal strings.
- `Company.compliance_status` (unchanged field on the base `Company`) is
  expected to hold one of `ComplianceStatus`'s values, computed from
  whether any canary covering the company's tasks has triggered - not a
  certification label like the current mock value ("SOC2 compliant").

`frontend/src/types/contract.ts` mirrors `rfc/frontend_models.py` 1:1 for
the frontend; the Python dataclasses are canonical.

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
| GET | `/api/ioms` | `IOM[]` | IOM leaf labels + coverage lookup (rarely changes; fine to fetch once and cache) |
| GET | `/api/canary-types` | `CanaryType[]` | Canary node labels/icons (rarely changes) |

Nice-to-have, not blocking the PoC:
- `GET /api/companies/{company_id}/summary` - precomputed counts (task
  count, canary count by health, triggered count) so the dashboard list
  doesn't need to fan out N+1 requests per company.

## Task creation pipeline

`POST /api/companies/{company_id}/tasks` (`{"prompt": string}`) is expected
to, synchronously before responding:
1. Create the `Task` and assign `iom_ids` (the compliance-mapping step).

Then, asynchronously (i.e. don't block the response on this):
2. For each mapped IOM with at least one `linked_canary_type_id`, generate
   a `CanaryInstance` row (`deployment_health: "pending"`) - IOMs with no
   linked canary type stay uncovered gaps, same as the seed data's IOM "6"
   and "7".
3. Deploy each generated instance, flipping it to
   `deployment_health: "active"` (or `"degraded"`/`"offline"` if that
   fails) once it's live.

The frontend polls `GET /tasks/{task_id}/canary-instances` every second
after creating a task (and while viewing any task with `pending` instances)
until every returned instance has left `"pending"`, then stops. It never
assumes a fixed instance count up front - new rows appearing mid-poll is
exactly how "canaries are still being generated" is expected to look.
`frontend/src/api/mockPipeline.ts` is a mock stand-in for all of this
(fake IOM mapping, staggered generation, delayed deploy) so the create-task
UI has something to poll against before the real pipeline exists.

## Open questions for backend

1. Auth: none assumed yet for the PoC - is there a token/session to plumb
   through later?
2. Is `CanaryInstance.metadata` meant to carry type-specific fields (e.g. a
   Website canary's HTML template, a Credential canary's seeded key) that
   the frontend should render, or is it backend-internal?
3. Should `IOM.linked_canary_type_ids` containing `""` (see IOM id `"2"` in
   `data.py`) be treated as "no canary type covers this yet", or is that a
   data bug to clean up?
