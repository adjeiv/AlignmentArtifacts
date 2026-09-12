# Alignment Artifacts

## Running locally

Three processes, wired together. No cloud infra required for a working local demo.

### 1. Backend

Needs `ANTHROPIC_API_KEY` set (used by `classify_task_ioms` and
`deploy_canary_instance` in `backend/agents.py`).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run main.py
```

Serves on `http://localhost:8000`.

### 2. Static site (Message board / Impersonation server / Fake answers canaries)

```bash
cd message-board
docker build -t message-board .
docker run -p 80:80 -p 443:443 -v "$(pwd)/content:/srv" message-board
```

Serves on `https://localhost/`.

**The `-v $(pwd)/content:/srv` bind mount is required, not optional.** The
Dockerfile's `COPY content/ /srv/` only bakes in whatever existed at
`docker build` time; without the bind mount, canaries deployed after that
build are written to disk (see `deploy_static_site` in `backend/agents.py`)
but never actually served.

### 3. Frontend

```bash
cd frontend
cp .env.example .env.local   # then set VITE_USE_MOCK=false
npm install
npm run dev
```

Serves on `http://localhost:5173`; Vite proxies `/api` to `http://localhost:8000`
by default (see `frontend/vite.config.ts`, override with `BACKEND_URL`).

### Trying it out

Open `localhost:5173`, create a task, watch the mind-map populate. Any
canary of type Impersonation server / Fake answers / Message board (every
type currently in `data.py`'s catalog) gets a real `target_url` of
`https://localhost/{instance_id}/` - open it in a browser to see the
generated page.

### Local-only caveats

- **The TLS cert is Caddy's local/internal CA, not a real one.** Caddy's
  automatic HTTPS via Let's Encrypt only works for a publicly resolvable
  domain reachable on ports 80/443 from the internet - not possible from a
  laptop behind NAT. `localhost` makes Caddy fall back to a
  self-signed-but-locally-trusted cert (expect a browser warning on first
  visit). A convincing real deployment needs an actual registered domain
  (e.g. `elsa-toys.com`) pointed at a publicly reachable host, with
  `DOMAIN=<that domain>` passed to the container instead.
- `deploy_noop` (the fallback for any canary type with no real deploy
  target) is currently unreachable given today's canary type catalog -
  every type in `data.py` already has a real handler in
  `CANARY_TYPE_HANDLERS`.
