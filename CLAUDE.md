# canarynet

AI safety auditing tool: companies register AI tasks, the system maps them
to Indicators of Misalignment (IOMs), generates + deploys canaries to detect
them, and a dashboard reports compliance status.

- Backend: FastAPI app at repo root (`backend/api.py`, `backend/models.py`,
  `backend/agents.py`, `data.py` as the in-memory store, `main.py` to run
  it). Everything runs directly via `uv` - no Docker.
- Frontend: Vite + React + TypeScript in `frontend/`, run via `npm`.
- `backend/agents.py` calls Claude by shelling out to the `claude` CLI
  (`run_claude()`, `claude -p ...`) rather than the Anthropic SDK - it
  authenticates however `claude` is already logged in on this machine, so
  there's no API key to configure anywhere in this repo.
- `POST /api/companies/{id}/tasks` runs the task-creation pipeline
  (frontend/CONTRACT.md): `classify_task_ioms` (IOM mapping) and
  `spawn_canary_instances_for_task` (one pending `CanaryInstance` per
  mapped-IOM x linked-canary-type pair) both run synchronously before
  responding, so the returned `Task` already has `iom_ids` and
  `GET .../canary-instances` is immediately non-empty. Only
  `deploy_canary_instance` (the slow, real `claude` CLI part - generating
  + placing each canary's artifact) is backgrounded, via FastAPI's
  `BackgroundTasks` + `asyncio.gather`.
- Canary types get their own deploy behavior via
  `CANARY_TYPE_HANDLERS` in `backend/agents.py` - most still resolve to
  `deploy_noop` (marks active, decorative `target_url`), but several canary
  types actually deploy for real via `deploy_static_site`, which gives the
  instance its own domain (`<slug>-<id>.canary.test`), writes the generated
  HTML into `static-site/content/<domain>/`, and registers the domain with
  `dns-resolver/` so it resolves. Served by the shared nginx container in
  `static-site/` (routes purely by Host header - see its `nginx.conf`), over
  HTTP always and HTTPS if the local CA in `pki/` is trusted. See README.md
  "Custom domains for canaries".
- Tasks seeded in `data.py` (ids "1"-"3") predate this pipeline - they have
  `iom_ids` but no `canary_instances`, so they show as coverage gaps until
  someone creates a new task through the UI.

## Running things

- `make install` - one-time setup: `uv sync` + `npm install` (frontend/).
- `make up` - run backend + frontend together in the foreground (Ctrl+C
  stops both). No API key needed - see above.
- `make backend` / `make frontend` - run just one half.
- `make test` - run the backend test suite (`uv run pytest`).

## The contract is the source of truth between frontend and backend

**`frontend/CONTRACT.md` is the API contract.** It documents every endpoint
the frontend calls (method, path, request/response shape), the derivation
rule for `Company.compliance_status`, and the task-creation pipeline's
expected behavior. `frontend/src/types/contract.ts` mirrors
`backend/models.py` 1:1 for the frontend side.

**Any backend change that touches the API surface must keep this contract
true**, not just keep the backend's own code self-consistent:

- Changing a `backend/models.py` dataclass's fields, a `backend/api.py`
  route's path/method/response shape, or the task-creation pipeline's
  behavior requires updating `frontend/CONTRACT.md` in the *same* change -
  not as a follow-up. If a change would make the contract inaccurate,
  either adjust the change to fit the contract, or update the contract and
  say so explicitly (don't let them silently drift apart).
- Before changing a route or model, read the relevant section of
  `frontend/CONTRACT.md` first, since it may describe intent that isn't
  obvious from the current code (e.g. the compliance-status derivation
  rule, or what an empty `GET /tasks/{id}/canary-instances` is guaranteed
  to mean).
- New fields should stay additive (defaults) where practical, matching how
  the contract was built up incrementally so far.

## Verify backend changes with tests

Any change to `backend/api.py`, `backend/models.py`, `backend/agents.py`,
or `data.py` should be checked with unit tests in `tests/`, run via
`uv run pytest`.

- `tests/test_api_contract.py` exercises the API against
  `frontend/CONTRACT.md` structurally (status codes, response shape, the
  fields the frontend actually reads). Extend it - or add a new test module
  - when you add/change a route or a response field, rather than only
  eyeballing it.
- `tests/test_agents.py` covers the pipeline functions directly
  (`classify_task_ioms`, `spawn_canary_instances_for_task`,
  `deploy_canary_instance`, the `CANARY_TYPE_HANDLERS` registry) and
  `run_claude` itself.
- Tests must never invoke the real `claude` CLI (slow, costs real usage,
  and won't run in an environment that isn't logged in) - mock
  `subprocess.run` or monkeypatch `backend.agents.run_claude` directly, or
  monkeypatch `backend.api.classify_task_ioms` /
  `backend.api.spawn_canary_instances_for_task` /
  `backend.api.deploy_canary_instance` for routes that depend on them
  (see both test files for examples of each).
- Run `uv run pytest` before considering a backend change done.
