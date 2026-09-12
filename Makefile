.PHONY: install up backend frontend test

# One-time (or after pulling dependency changes): installs both halves.
install:
	uv sync
	cd frontend && npm install

# Run backend + frontend together in the foreground (Ctrl+C stops both).
# No API key to set - the backend authenticates via the `claude` CLI
# however it's already logged in on this machine.
up:
	@lsof -t -i:8000 -i:5173 2>/dev/null | xargs -r kill -9 2>/dev/null || true
	@trap 'kill 0' EXIT; \
	(uv run python main.py) & \
	(cd frontend && VITE_USE_MOCK=false npm run dev) & \
	wait

# Just the backend: http://localhost:8000
backend:
	uv run python main.py

# Just the frontend dev server against the local backend: http://localhost:5173
frontend:
	cd frontend && VITE_USE_MOCK=false npm run dev

# Backend test suite (see CLAUDE.md).
test:
	uv run pytest
