# Alignment Artifacts

## Configuration

Copy `.env.example` to `.env` and fill in whichever optional vars you want
(`GITHUB_TOKEN`, `THINKST_ALERT_EMAIL` - see their sections below). That one
`.env` is read automatically by both `uv run main.py`/`make up` (via
`python-dotenv`, loaded at the top of `main.py`) and `docker compose up`
(Compose loads a root `.env` on its own) - no need to `export` anything or
keep two copies in sync. `export`ing still works too, if you'd rather not
have a `.env` file at all.

## Running locally

### Quickest: docker compose

```bash
docker compose up --build
```

Starts all five services (backend, static-site, dns-resolver, log-monitor,
frontend) wired together via `docker-compose.yml`, sharing a
`canary-content` volume so canaries `deploy_static_site` writes in the
backend container immediately show up served by the static-site container.
Frontend on `http://localhost:5173`, backend on `http://localhost:8000`. See
"Custom domains for canaries" below before expecting a canary's
`target_url` to actually load.

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

### Real credential canaries (Thinkst Canarytokens)

Every deployed static-site canary also gets a `.env` file
(`_plant_fake_env` in `backend/agents.py`) alongside its `index.html`, with
real, third-party-monitored credentials spliced in via
[canarytokens.org](https://docs.canarytokens.org/guide/)'s free public API
(Thinkst's open-source Canarytokens project) - an AWS key pair and a plain
URL today. Unlike everything else in this repo, *using* one of these (an
actual AWS API call, a fetch of the planted URL) is detected by Thinkst's
infrastructure, not ours - `backend/agents.py`'s `run_thinkst_poller`
periodically asks canarytokens.org whether a planted token has fired and
triggers the same way a `log-monitor` hit does.

This is opt-in and off by default - **set `THINKST_ALERT_EMAIL`** to an
email address you actually control before starting the backend:

```bash
export THINKST_ALERT_EMAIL=you@example.com
uv run main.py
```

Without it, `.env` planting silently no-ops (same pattern as `deploy_noop`
for canary types with nothing real configured yet) - deploys still succeed,
just without a `.env`. Thinkst requires an email or webhook per token even
though this integration only ever polls `/history` itself and never relies
on that channel actually firing, so expect Thinkst's own alert emails to
land in that inbox too when a token fires.

### GitHub repository canaries

The "GitHub repository" canary type (`CanaryType` id "5") writes into ONE
real, public, **operator-created** GitHub repo - every canary instance gets
its own folder (`canaries/<slug>-<id>/README.md`) in that shared repo,
rather than a fresh repo per instance. See `backend/github_canary.py` for
why: it lets `GITHUB_TOKEN` be a **fine-grained PAT scoped to just that one
repo** (Contents, Issues, Pull requests: read & write) instead of a
classic, repo-creating token with much broader access.

Setup (one-time, manual):

1. Create a public repo by hand on GitHub (under a dedicated bot/throwaway
   account, not your own - see below).
2. Create a fine-grained PAT scoped to just that repo, with Contents,
   Issues, and Pull requests all set to Read & write (Metadata read-only
   is required automatically).
3. Set both in `.env`:
   ```
   GITHUB_TOKEN=github_pat_...
   GITHUB_REPO_FULL_NAME=your-bot-account/that-repo
   ```

Each deploy seeds three things into that repo:

- a fake "leaked solutions" README under the instance's folder (the
  LLM-generated artifact, same as every other canary type),
- an issue + comment thread where a real Thinkst AWS credential gets pasted
  into a "here's my error log, can someone help debug" comment - closer to
  how credentials actually leak than a plain `.env` file (needs
  `THINKST_ALERT_EMAIL` set too; skipped otherwise),
- once per repo (not per instance - see `_seed_stray_pull_request_once`),
  one small stray pull request of its own, so the repo isn't sitting at a
  suspiciously pristine zero-PRs state.

`run_github_poller` checks every `GITHUB_POLL_INTERVAL_SECONDS` (default
1800s) whether any pull request numbered after an instance's baseline
touches that instance's folder, and triggers the canary the same way a
`log-monitor`/Thinkst hit does. **Clone/view traffic is not used as a
signal** - GitHub's traffic API is per-repo, not per-folder, so once
multiple canaries share one repo it can no longer be attributed to a
specific instance; this was a deliberate fidelity tradeoff made when
moving from one-fresh-repo-per-instance to one-shared-repo (see the
module's docstring). The planted credential is unaffected and still
caught precisely by Thinkst's own poller the moment it's actually used.

**This is opt-in and creates a real public artifact under a real GitHub
account** - a repo you write to this way is genuinely visible on
github.com, counts against that account's API rate limit, and needs
manual cleanup (deleting content isn't automated). Use a dedicated
bot/throwaway account, not your own: the seeded content is deliberately
written to look like a careless leak (a sloppy README, an issue comment
saying "pasting my env, I know I know" with fake credentials in it) - not
something you want publicly attached to your real identity.

Without both `GITHUB_TOKEN` and `GITHUB_REPO_FULL_NAME` set,
`deploy_github_repo` falls back to a decorative no-op, same
pattern as `deploy_noop` and the Thinkst integration above.

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
