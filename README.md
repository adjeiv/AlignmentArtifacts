# Alignment Artifacts

## Running locally

### Quickest: docker compose

```bash
docker compose up --build
```

Starts all four services (backend, static-site, dns-resolver, frontend)
wired together via `docker-compose.yml`, sharing a `canary-content` volume so
canaries `deploy_static_site` writes in the backend container immediately
show up served by the static-site container. Frontend on
`http://localhost:5173`, backend on `http://localhost:8000`. See "Custom
domains for canaries" below before expecting a canary's `target_url` to
actually load.

No API key to set - like the manual backend below, the containerized backend
calls Claude via the `claude` CLI (see CLAUDE.md), so it needs `claude`
installed and logged in *inside the backend container* to actually deploy
canaries; that isn't wired up by `backend/Dockerfile` yet, so containerized
deploys will fail until it is. Running the backend manually (below) is the
reliable path today.

### Manual: three separate processes

Useful for iterating on one piece without rebuilding a container each time.

#### 1. Backend

No API key needed - `classify_task_ioms` and `deploy_canary_instance` in
`backend/agents.py` shell out to the `claude` CLI, authenticated however
it's already logged in on this machine.

```bash
uv run main.py
```

Serves on `http://localhost:8000`.

#### 2. Static site (Message board / Impersonation server / Fake answers canaries)

Needs the DNS resolver alongside it for canary domains to resolve at all -
see "Custom domains for canaries" below for the full picture. Manually:

```bash
cd static-site && docker build -t static-site . && docker run \
  -p 80:80 -p 443:443 \
  -v "$(pwd)/content:/srv" \
  -v "$(pwd)/../pki/out:/etc/nginx/certs:ro" \
  static-site
cd ../dns-resolver && docker build -t dns-resolver . && docker run \
  -p 127.0.0.1:53:53/udp \
  -v "$(pwd)/zones.json:/data/zones.json" \
  dns-resolver
```

**The `content:/srv` bind mount is required, not optional** - without it,
canaries `deploy_static_site` writes after the image is built are never
actually served.

#### 3. Frontend

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
type currently in `data.py`'s catalog) gets a real `target_url` on its own
`*.canary.test` domain - see "Custom domains for canaries" below to make
that actually resolve and load.

### Custom domains for canaries

Each static-site canary (Impersonation server / Fake answers / Message
board) gets its own domain, e.g. `elsa-toys-support-a1b2c3d4.canary.test`
(`_canary_domain` in `backend/agents.py`), not a shared `localhost` path.
Three pieces make that resolve and load in a browser:

- **nginx** (`static-site/`) routes purely by Host header
  (`static-site/nginx.conf`'s `map`) to `/srv/<domain>/index.html` - no
  per-domain nginx config or reload on deploy, just a directory
  `deploy_static_site` writes.
- **dns-resolver** (`dns-resolver/resolver.py`) is a small Python DNS server.
  It answers `A` queries for canary domains out of a shared `zones.json`
  (which `deploy_static_site` updates on every deploy) and forwards
  everything else upstream to `8.8.8.8` - so pointing your Mac at it doesn't
  break normal browsing.
- **pki/** holds a local CA + a wildcard cert for `*.canary.test`, mounted
  into the nginx container, so HTTPS works without per-domain certs.

Setup (macOS; all one-time except `dns-use`/`dns-restore`, which you toggle
per session):

```bash
make ca-generate        # generates pki/out/ca.pem + wildcard cert
make ca-trust            # trusts that CA system-wide (sudo, System keychain)
docker compose up --build   # backend + static-site (nginx) + dns-resolver + frontend
make dns-use              # points this Mac's DNS at the dns-resolver container (sudo)
```

Then create a task via the UI and open a canary's `target_url` -
`https://<domain>/` - directly in the browser.

**When you're done**, undo the DNS change (containers stopping doesn't undo
it, and a dead resolver means no DNS at all for this Mac):

```bash
make dns-restore
```

`make ca-untrust` reverses the CA trust the same way, if you want that gone
too.

### Local-only caveats

- **Skip `ca-trust` and canaries still work over plain HTTP** -
  `http://<domain>/` - nginx serves both; only HTTPS needs the CA trusted.
  Browsers will show a security warning for HTTPS until you run it.
- **`dns-use` repoints DNS for the whole machine**, not just canary domains -
  the resolver forwards anything it doesn't recognize upstream, but if the
  `dns-resolver` container isn't running, this Mac loses DNS entirely until
  you run `make dns-restore`.
- This is all `.canary.test` (IANA-reserved for testing, never resolves for
  real) plus a locally-trusted CA - not a substitute for a real registered
  domain (e.g. `elsa-toys.com`) on a publicly reachable host, which is what
  a convincing non-local deployment would need instead.
- `deploy_noop` (the fallback for any canary type with no real deploy
  target) is currently unreachable given today's canary type catalog -
  every type in `data.py` already has a real handler in
  `CANARY_TYPE_HANDLERS`.
