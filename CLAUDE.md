# canarynet

AI safety auditing tool: companies register AI tasks, the system maps them
to Indicators of Misalignment (IOMs), generates + deploys canaries to detect
them, and a dashboard reports compliance status.

- Backend: FastAPI app at repo root (`rfc/api.py`, `rfc/models.py`,
  `rfc/agents.py`, `data.py` as the in-memory store, `main.py` to run it).
  Everything runs directly via `uv` - no Docker.
- Frontend: Vite + React + TypeScript in `frontend/`, run via `npm`.
- `rfc/agents.py` calls Claude by shelling out to the `claude` CLI
  (`run_claude()`, `claude -p ...`) rather than the Anthropic SDK - it
  authenticates however `claude` is already logged in on this machine, so
  there's no API key to configure anywhere in this repo. Each call is
  noticeably slower than a raw API call (the CLI harness itself has
  startup overhead) - a structured `--json-schema` prediction call has
  been observed taking ~80-100s. Because of that,
  `GET /api/tasks/{id}/canary-instances` never runs the pipeline inline:
  `ensure_pipeline_started()` kicks it off in a background thread (once per
  task, guarded against duplicate starts) and the route always returns
  immediately with whatever's in the store so far - the frontend's polling
  is what surfaces the canaries as they land.

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
expected behavior. `frontend/src/types/contract.ts` mirrors `rfc/models.py`
1:1 for the frontend side.

**Any backend change that touches the API surface must keep this contract
true**, not just keep the backend's own code self-consistent:

- Changing a `rfc/models.py` dataclass's fields, an `rfc/api.py` route's
  path/method/response shape, or the task-creation pipeline's behavior
  requires updating `frontend/CONTRACT.md` in the *same* change - not as a
  follow-up. If a change would make the contract inaccurate, either adjust
  the change to fit the contract, or update the contract and say so
  explicitly (don't let them silently drift apart).
- Before changing a route or model, read the relevant section of
  `frontend/CONTRACT.md` first, since it may describe intent that isn't
  obvious from the current code (e.g. the compliance-status derivation
  rule, or the async pipeline semantics `/tasks/{id}/canary-instances`
  polling depends on).
- New fields should stay additive (defaults) where practical, matching how
  the contract was built up incrementally so far.

## Verify backend changes with tests

Any change to `rfc/api.py`, `rfc/models.py`, `rfc/agents.py`, or `data.py`
should be checked with unit tests in `tests/`, run via `uv run pytest`.

- `tests/test_api_contract.py` exercises the API against
  `frontend/CONTRACT.md` structurally (status codes, response shape, the
  fields the frontend actually reads). Extend it - or add a new test module
  - when you add/change a route or a response field, rather than only
  eyeballing it.
- Tests must never invoke the real `claude` CLI (slow, costs real usage,
  and won't run in an environment that isn't logged in) - mock
  `subprocess.run` (see `tests/test_agents.py`) or monkeypatch
  `rfc.agents.run_claude`/`rfc.api.ensure_pipeline_started` for anything
  upstream of it (see `tests/test_api_contract.py`), depending on what the
  test needs to exercise.
- If you touch `ensure_pipeline_started` (or anything it calls), keep
  `tests/test_agents.py::test_ensure_pipeline_started_does_not_block_and_is_idempotent`
  passing - that's what pins down "the route never blocks, and polling the
  same task twice never starts the pipeline twice".
- Run `uv run pytest` before considering a backend change done.
