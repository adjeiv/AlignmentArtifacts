# Alignment Artifacts

## Running locally

The backend and frontend always run directly on the host, never in Docker -
the backend authenticates to Claude via the `claude` CLI however it's
already logged in on this machine (see CLAUDE.md), and that doesn't carry
into a container. Docker is only for the canary-serving infra: static-site's
nginx, the DNS resolver, and log-monitor.

#### 1. Backend

```bash
uv run main.py
```

Serves on `http://localhost:8000`. No API key needed - `classify_task_ioms`
and `deploy_canary_instance` in `backend/agents.py` shell out to the
`claude` CLI, authenticated however it's already logged in on this machine.

#### 2. Canary infra: static-site + dns-resolver + log-monitor

```bash
docker compose up --build
```

Starts all three (`docker-compose.yml`), bind-mounted straight to the same
local paths the host-run backend above writes to by default
(`static-site/content`, `dns-resolver/zones.json`, `log-monitor/endpoints.json`,
`pki/out`) - no named volume or extra wiring needed. See "Custom domains for
canaries" below before expecting a canary's `target_url` to actually load in
a browser (DNS resolution and CA trust are both separate, one-time setup
steps).

Prefer to run these without Docker, or iterate on just one piece? See
CLAUDE.md's "Full system ... on Linux" section for the plain `docker run` /
host-process equivalent of each.

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
type currently in `data.py`'s catalog) gets a real `target_url` on its own,
model-invented domain (e.g. `brightpath-vendor-support.com`, not a
`localhost` path or anything derived mechanically from the task) - see
"Custom domains for canaries" below to make that actually resolve and load.

### Custom domains for canaries

Each static-site canary (Impersonation server / Fake answers / Message
board) gets its own domain - the model invents one to go with the page it's
generating (`SiteArtifact.domain`, alongside `SiteArtifact.html`, in
`backend/agents.py`), falling back to a deterministic
`<slug>-<id>.canary.test` one if that invented domain is invalid or
collides with an already-deployed one (see `_sanitize_domain`,
`_register_dns_zone`). So a domain is arbitrary, not confined to any one
TLD - three pieces make whatever it turns out to be resolve and load in a
browser:

- **nginx** (`static-site/`) routes by Host header
  (`static-site/nginx.conf`'s `map`) to `/srv/<domain>/index.html` - no
  per-domain nginx config or reload on deploy, just a directory
  `deploy_static_site` writes. The regex accepts any syntactically valid
  hostname now, not one fixed suffix - it's also the security boundary
  against a manipulated Host header path-traversing out of `/srv`.
- **dns-resolver** (`dns-resolver/resolver.py`) is a small Python DNS server.
  It answers `A` queries for whatever domains are in a shared `zones.json`
  (which `deploy_static_site` updates on every deploy - not scoped to any
  TLD either) and forwards everything else upstream unchanged, trying each
  server in `DNS_UPSTREAM` (comma-separated) in order - so put this
  machine's *own* normal DNS server(s) first and a public resolver last, and
  pointing your DNS at it doesn't break normal browsing even if one
  upstream is unreachable.
- **pki/** holds a local CA (`make ca-generate`). `deploy_static_site` uses
  it to issue a fresh leaf cert per deployed domain
  (`_issue_leaf_cert`) - not one shared wildcard cert, since arbitrary
  domains can't all be covered by a single cert's SAN list the way
  `*.canary.test` could. Trusting the CA once still covers every canary
  regardless of its domain, since every leaf cert chains back to the same
  CA. nginx picks the right cert/key per-connection via SNI
  (`static-site/nginx.conf`'s `$ssl_server_name` map), falling back to a
  static wildcard cert (covering only the `<slug>-<id>.canary.test`
  fallback domains) for anything unmapped or not yet issued.

Setup (macOS; all one-time except `dns-use`/`dns-restore`, which you toggle
per session - **Linux**: `make ca-trust`/`make dns-use` shell out to
macOS-only tools, see CLAUDE.md's "Full system ... on Linux" section for the
equivalent):

```bash
make ca-generate        # generates pki/out/ca.pem (the CA every leaf cert is signed by)
make ca-trust            # trusts that CA system-wide (sudo, System keychain)
docker compose up --build   # static-site (nginx) + dns-resolver + log-monitor
make dns-use              # points this Mac's DNS at the dns-resolver container (sudo)
```

(Also run the backend and frontend - see "Running locally" above; they're
never part of `docker compose`.) Then create a task via the UI and open a
canary's `target_url` - `https://<domain>/` - directly in the browser.

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
  since canary domains are now arbitrary rather than confined to one TLD,
  there's no narrower domain to scope this to. The resolver forwards
  anything it doesn't recognize upstream (see `DNS_UPSTREAM` above), but if
  the `dns-resolver` container isn't running, this Mac loses DNS entirely
  until you run `make dns-restore`.
- A model-invented domain is still purely local - `zones.json` and this
  machine's (re)pointed DNS are the only reason it resolves at all, and the
  CA is only trusted on this machine. It isn't a substitute for a real
  registered domain on a publicly reachable host, which is what a
  convincing non-local deployment would need instead - and if the model
  happens to invent a domain that's *actually* registered by someone else,
  this setup never talks to it (DNS_ZONES_FILE wins over any upstream
  answer for a domain it lists) or to the real Internet.
- `deploy_noop` (the fallback for any canary type with no real deploy
  target) is currently unreachable given today's canary type catalog -
  every type in `data.py` already has a real handler in
  `CANARY_TYPE_HANDLERS`.
