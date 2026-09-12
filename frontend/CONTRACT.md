# Frontend <-> Backend consumer contract

Status: **draft, for review**. This is what the frontend needs from the API;
please push back on anything that doesn't fit the backend's plans.

## Data model

The frontend's fields have been folded into `rfc/models.py` directly (there's
no longer a separate `rfc/frontend_models.py` - that file's proposed
extensions are now the real `Task` and `CanaryInstance` dataclasses):

- `Task.iom_ids: list[str]` - the IOMs this task has been mapped to. Drives
  the mind-map view's branches.
- `CanaryInstance.task_id`, `.iom_ids`, `.deployment_health`, `.triggered`,
  `.triggered_iom_id`, `.deployed_at`, `.last_heartbeat_at`, `.target_url`.
  A canary instance is deployed against one task and covers detection for a
  subset of that task's `iom_ids`.
- `CanaryEvent` dataclass - the log/trigger stream for one canary
  instance. A `level == "trigger"` event is what flips
  `CanaryInstance.triggered` and names the detected `iom_id`.
- `ComplianceStatus`, `DeploymentHealth`, `LogLevel` enums - plain `str`
  enums so they serialize as normal strings.
- `Company.compliance_status` is expected to hold one of `ComplianceStatus`'s
  values, computed from whether any canary covering the company's tasks has
  triggered - not a certification label like the old mock value ("SOC2
  compliant"). The API computes this per-request rather than trusting the
  stored field (see `rfc/api.py`).

`frontend/src/types/contract.ts` mirrors `rfc/models.py` 1:1 for the
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

## Open questions for backend

1. Auth: none assumed yet for the PoC - is there a token/session to plumb
   through later?
2. Is `CanaryInstance.metadata` meant to carry type-specific fields (e.g. a
   Website canary's HTML template, a Credential canary's seeded key) that
   the frontend should render, or is it backend-internal?
3. Should `IOM.linked_canary_type_ids` containing `""` (see IOM id `"2"` in
   `data.py`) be treated as "no canary type covers this yet", or is that a
   data bug to clean up?
