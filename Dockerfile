# Backend (FastAPI, served by uvicorn). See docker-compose.yml for how this
# is wired to the frontend; frontend/Dockerfile is the other image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py data.py ./
COPY rfc ./rfc

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "rfc.api:app", "--host", "0.0.0.0", "--port", "8000"]
