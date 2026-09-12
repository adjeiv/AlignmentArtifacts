# canarynet

AI safety auditing tool: companies register AI tasks, the system maps them
to Indicators of Misalignment (IOMs), generates + deploys canaries to detect
them, and a dashboard reports compliance status.

- Backend: FastAPI app at repo root (`rfc/api.py`, `rfc/models.py`,
  `rfc/agents.py`, `data.py` as the in-memory store, `main.py` to run it).
- Frontend: Vite + React + TypeScript in `frontend/`.
- `docker-compose.yml` runs both together.

## Running things

- `make up` - build and run the full stack (frontend + backend) via
  Docker Compose. Requires `ANTHROPIC_API_KEY` - copy `.env.example` to
  `.env` and fill it in first (see `docker-compose.yml`).
- `make down` - stop the stack.
- `make build` - build the images without starting them.
- `make logs` - tail logs from both containers.
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
- Tests must not require a real `ANTHROPIC_API_KEY` or make live Anthropic
  API calls - `rfc/agents.py`'s `generate_all` (used by
  `/api/tasks/{id}/canary-instances`) calls the Anthropic API for real, so
  tests that exercise that route monkeypatch it. Follow that pattern for
  any other route that ends up depending on `agents.py`.
- Run `uv run pytest` before considering a backend change done.
