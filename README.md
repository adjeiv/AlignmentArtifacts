# canarynet

AI safety auditing tool - see `CLAUDE.md` for the architecture and
`frontend/CONTRACT.md` for the API contract between the two halves.

## Run everything together

```bash
make install   # one-time: uv sync + npm install
make up        # backend (http://localhost:8000) + frontend (http://localhost:5173)
```

No API key needed - `rfc/agents.py` calls Claude via the `claude` CLI, which
authenticates however it's already logged in on this machine. Viewing a
task's canary instances for the first time runs the real prediction +
artifact-generation pipeline, which can take a while (see CLAUDE.md).

`make up` runs both in the foreground; Ctrl+C stops both. `make backend` /
`make frontend` run just one half - see `frontend/README.md` to instead run
the frontend against its built-in mock data (no backend needed at all).

## Backend only

```bash
uv run python main.py   # http://localhost:8000
uv run pytest            # backend test suite
```
