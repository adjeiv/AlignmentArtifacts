# canarynet

AI safety auditing tool - see `CLAUDE.md` for the architecture and
`frontend/CONTRACT.md` for the API contract between the two halves.

## Run everything together

```bash
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
docker compose up --build
```

- Frontend: http://localhost:8080 (talks to the real backend, not the mock data)
- Backend: http://localhost:8000

`ANTHROPIC_API_KEY` is required - `rfc/agents.py` calls the real Anthropic
API (not mocked) whenever the frontend asks for a task's canary instances,
which costs real tokens/time. See `frontend/README.md` to instead run just
the frontend against its built-in mock data.

## Backend only, locally (no Docker)

```bash
uv run python main.py        # http://localhost:8000
uv run pytest                # backend test suite
```
