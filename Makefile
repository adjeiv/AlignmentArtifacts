.PHONY: up down build logs test

# Run the full stack (frontend + backend), building images if needed.
# Requires ANTHROPIC_API_KEY - copy .env.example to .env and fill it in.
up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# Backend test suite (see CLAUDE.md).
test:
	uv run pytest
