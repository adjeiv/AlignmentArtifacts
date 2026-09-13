# canarynet

AI safety auditing tool: companies register AI tasks, the system maps them
to Indicators of Misalignment (IOMs), generates + deploys canaries to detect
them, and a dashboard reports compliance status.

- Backend: FastAPI app at repo root (`backend/api.py`, `backend/models.py`,
  `backend/agents.py`, `data.py` as the in-memory store, `main.py` to run
  it). Everything runs directly via `uv` - no Docker.
- Config: optional env vars (`GITHUB_TOKEN`, `THINKST_ALERT_EMAIL`, ...) come
  from a root `.env` (see `.env.example`) - `main.py` calls `load_dotenv()`
  before importing `backend.api`, since `backend/agents.py`,
  `backend/thinkst.py`, and `backend/github_canary.py` all read their config
  as module-level `os.environ.get(...)` constants at import time. `docker
  compose up` reads the same root `.env` on its own.
- Frontend: Vite + React + TypeScript in `frontend/`, run via `npm`.
- `backend/agents.py` calls Claude by shelling out to the `claude` CLI
  (`run_claude()`, `claude -p ...`) rather than the Anthropic SDK - it
  authenticates however `claude` is already logged in on this machine, so
  there's no API key to configure anywhere in this repo.
- `POST /api/companies/{id}/tasks` runs the task-creation pipeline
  (frontend/CONTRACT.md): `classify_task_ioms` (IOM mapping) and
  `spawn_canary_instances_for_task` (one pending `CanaryInstance` per
  mapped-IOM x linked-canary-type pair) both run synchronously before
  responding, so the returned `Task` already has `iom_ids` and
  `GET .../canary-instances` is immediately non-empty. Only
  `deploy_canary_instance` (the slow, real `claude` CLI part - generating
  + placing each canary's artifact) is backgrounded, via FastAPI's
  `BackgroundTasks` + `asyncio.gather`.
- Canary types get their own deploy behavior via
  `CANARY_TYPE_HANDLERS` in `backend/agents.py` - most still resolve to
  `deploy_noop` (marks active, decorative `target_url`), but several canary
  types actually deploy for real via `deploy_static_site`. Those types'
  `build_prompt` also carries an `output_schema=SiteArtifact` - the model
  invents both the page *and* the domain it lives at together (`SiteArtifact
  {domain, html}`), so the domain actually matches the page's branding
  instead of being a mechanical slug. `_sanitize_domain` falls back to a
  deterministic `<slug>-<id>.canary.test` domain when the model's choice is
  syntactically invalid, and `_register_dns_zone` falls back to it too on a
  collision with an already-deployed domain (rare, but arbitrary invented
  domains aren't guaranteed unique the way slug+id always was). Whichever
  domain wins: `deploy_static_site` writes the generated HTML into
  `static-site/content/<domain>/`, registers the domain with `dns-resolver/`
  so it resolves, and issues it its own TLS cert signed by the local CA in
  `pki/` (`_issue_leaf_cert` - skipped, silently, if that CA hasn't been
  generated). Served by the shared nginx container in `static-site/` (routes
  purely by Host/SNI - see its `nginx.conf`), over HTTP always and HTTPS
  wherever a cert exists. See README.md "Custom domains for canaries".
- Triggering: `deploy_static_site` also registers each instance's
  (IOM, path-regex) pairs into a shared `endpoints.json`
  (`_register_endpoints`, `_canary_endpoint_regex` - one regex per canary
  type). `log-monitor/monitor.py` tails the static-site container's nginx
  access log and, on a match, calls
  `POST /api/canary-instances/{id}/trigger/{iom_id}` - this flips
  `triggered`/`triggered_iom_id` and logs a `CanaryEvent`.
  `Company.compliance_status` is computed live from `triggered` on every
  read, so nothing else needs telling about a hit.
- Real credential canaries: `deploy_static_site` also plants a `.env` file
  (`_plant_fake_env`) containing real Thinkst Canarytokens
  (canarytokens.org's free public API - see `_create_canarytoken`), and
  registers `/.env` as one of the instance's endpoint regexes. This needs
  `THINKST_ALERT_EMAIL` set (some email you control - Thinkst requires one
  per token even though we only ever poll, never rely on it firing);
  unset means it silently no-ops. `run_thinkst_poller`, started from
  `backend/api.py`'s app `lifespan`, polls each planted token's
  `/history` every `THINKST_POLL_INTERVAL_SECONDS` (default 30s) and
  calls the same `trigger_canary_instance` as the nginx-log path - this
  is a separate detection mechanism because credential *use* is outbound
  (an AWS API call, a webhook fetch), not a request to our own nginx.
- GitHub repository canaries (`CanaryType` id "5"): `backend/github_canary.py`
  writes into ONE operator-created, pre-existing repo (`GITHUB_REPO_FULL_NAME`)
  - a folder per canary instance (`_instance_folder`), not a fresh repo per
  instance - specifically so `GITHUB_TOKEN` can be a fine-grained PAT scoped
  to just that repo instead of a classic, repo-creating token. Each deploy
  seeds a "leaked solutions" README in its folder, an issue + comment thread
  with a Thinkst AWS credential pasted into a "here's my error log" comment
  (`_seed_credential_issue`), and (once per repo, not per instance -
  `_seed_stray_pull_request_once`) one small stray PR so the repo isn't
  pristine. Kept as its own module rather than folded into
  `backend/agents.py` since it owns a distinct external service, auth, and
  poller. `run_github_poller` (also started from `backend/api.py`'s
  `lifespan`) checks every `GITHUB_POLL_INTERVAL_SECONDS` (default 1800s)
  whether a PR numbered after an instance's baseline touches that instance's
  folder (`_new_pull_request_touches_folder`) - clone/view traffic is
  deliberately NOT used as a trigger signal since GitHub's traffic API is
  per-repo, not per-folder, so it can't be attributed to one instance once
  they share a repo. Unset `GITHUB_TOKEN`/`GITHUB_REPO_FULL_NAME` means
  `deploy_github_repo` falls back to the same decorative no-op as
  `deploy_noop`. See README.md "GitHub repository canaries" before enabling
  - this creates a real public artifact under a real account.
- `backend/thinkst.py` holds the Thinkst Canarytokens client
  (`create_canarytoken`, `register_token`, `poll_thinkst_tokens_once`,
  `run_thinkst_poller`) - split out of `backend/agents.py` so both
  `deploy_static_site`'s `.env` and `github_canary.py`'s issue/comment
  seeding can use it without a circular import.
- Tasks seeded in `data.py` (ids "1"-"3") predate this pipeline - they have
  `iom_ids` but no `canary_instances`, so they show as coverage gaps until
  someone creates a new task through the UI.

## Running things

- `make install` - one-time setup: `uv sync` + `npm install` (frontend/).
- `make up` - run backend + frontend together in the foreground (Ctrl+C
  stops both). No API key needed - see above.
- `make backend` / `make frontend` - run just one half.
- `make test` - run the backend test suite (`uv run pytest`).

### Full system (canary domains: nginx + DNS resolver + CA) on Linux

README.md's "Custom domains for canaries" section is macOS-only -
`make ca-trust` shells out to macOS's `security`, and `make dns-use`
(`scripts/mac-dns.sh`) to macOS's `networksetup`/`route`. Confirmed working
end-to-end on Linux (NetworkManager + systemd-resolved) like this instead:

1. `make ca-generate` - portable, generates `pki/out/ca.pem` (the CA
   `_issue_leaf_cert` in `backend/agents.py` signs every deployed domain's
   cert with).
2. Backend and frontend run on the host - **always**, never in Docker (see
   `docker-compose.yml`'s header comment: the containerized path was tried
   and dropped because the `claude` CLI login doesn't carry into a
   container). `make backend` / `make frontend` (or `make up` for both).
3. `docker compose up --build` for static-site + dns-resolver + log-monitor
   - `docker-compose.yml` already bind-mounts the exact local paths the
   host-run backend above writes to by default (`static-site/content`,
   `dns-resolver/zones.json`, `log-monitor/endpoints.json`, `pki/out`), so
   this needs no extra flags or an override file - just make sure
   `dns-resolver/zones.json` and `log-monitor/endpoints.json` exist first
   (`echo '{}' > <path>`) since Docker bind-mounting a *file* that doesn't
   exist yet creates a directory there instead, which then breaks the
   backend's own read/write to that same path.
4. DNS - `SiteArtifact.domain` (`backend/agents.py`) is model-invented and
   arbitrary, not scoped to one TLD, so unlike a single-suffix setup there's
   no fixed domain to scope a routing-only DNS rule to - the dns-resolver
   container has to become the connection's actual nameserver. Before doing
   that, capture this machine's *current* DNS server(s) (`resolvectl status`
   - e.g. a router at `192.168.0.1`) and pass them as `DNS_UPSTREAM`
   (comma-separated, tried in order - see `dns-resolver/resolver.py`)
   alongside a public resolver as a last-resort fallback when starting the
   stack in step 3, so anything not in `zones.json` (everything except our
   canaries) keeps resolving normally even though our resolver is now in the
   loop for every query: `DNS_UPSTREAM=192.168.0.1,8.8.8.8 docker compose up --build`.
   Then point the connection's DNS at it (NetworkManager, the
   systemd-resolved-native equivalent of what `mac-dns.sh` does with
   macOS's `networksetup`):
   `sudo nmcli connection modify <conn> ipv4.dns 127.0.0.1 ipv4.ignore-auto-dns yes
   && sudo nmcli connection up <conn>`
   (`<conn>` from `nmcli -t -f NAME,DEVICE connection show --active`; undo
   with `sudo nmcli connection modify <conn> ipv4.dns "" ipv4.ignore-auto-dns no
   && sudo nmcli connection up <conn>` to go back to DHCP-provided DNS).
5. CA trust, system-wide (Debian/Ubuntu):
   `sudo cp pki/out/ca.pem /usr/local/share/ca-certificates/canarynet-local-ca.crt
   && sudo update-ca-certificates` (undo: remove that file, rerun
   `update-ca-certificates`). One CA, trusted once, covers every canary's
   domain regardless of what it is - `_issue_leaf_cert` signs a fresh leaf
   cert per deployed domain with this same CA at deploy time, so trusting
   the CA itself is a one-time step, not something to redo per canary.
   Chrome/Chromium read the system store: this is enough for them.
   **Firefox keeps its own separate cert store** and will still warn on
   `https://<domain>/` regardless - import the CA into Firefox directly, or
   flip `security.enterprise_roots.enabled` in `about:config`, to cover it
   too. Skipping CA trust entirely still works - test over `http://<domain>/`
   instead of `https://`; canary triggering is identical either way
   (log-monitor matches on the nginx access log regardless of scheme).
   `openssl` needs to be on the host running the backend - true by default
   on most Linux/macOS dev machines, and already required for
   `make ca-generate` too.

## The contract is the source of truth between frontend and backend

**`frontend/CONTRACT.md` is the API contract.** It documents every endpoint
the frontend calls (method, path, request/response shape), the derivation
rule for `Company.compliance_status`, and the task-creation pipeline's
expected behavior. `frontend/src/types/contract.ts` mirrors
`backend/models.py` 1:1 for the frontend side.

**Any backend change that touches the API surface must keep this contract
true**, not just keep the backend's own code self-consistent:

- Changing a `backend/models.py` dataclass's fields, a `backend/api.py`
  route's path/method/response shape, or the task-creation pipeline's
  behavior requires updating `frontend/CONTRACT.md` in the *same* change -
  not as a follow-up. If a change would make the contract inaccurate,
  either adjust the change to fit the contract, or update the contract and
  say so explicitly (don't let them silently drift apart).
- Before changing a route or model, read the relevant section of
  `frontend/CONTRACT.md` first, since it may describe intent that isn't
  obvious from the current code (e.g. the compliance-status derivation
  rule, or what an empty `GET /tasks/{id}/canary-instances` is guaranteed
  to mean).
- New fields should stay additive (defaults) where practical, matching how
  the contract was built up incrementally so far.

## Verify backend changes with tests

Any change to `backend/api.py`, `backend/models.py`, `backend/agents.py`,
or `data.py` should be checked with unit tests in `tests/`, run via
`uv run pytest`.

- `tests/test_api_contract.py` exercises the API against
  `frontend/CONTRACT.md` structurally (status codes, response shape, the
  fields the frontend actually reads). Extend it - or add a new test module
  - when you add/change a route or a response field, rather than only
  eyeballing it.
- `tests/test_agents.py` covers the pipeline functions directly
  (`classify_task_ioms`, `spawn_canary_instances_for_task`,
  `deploy_canary_instance`, the `CANARY_TYPE_HANDLERS` registry) and
  `run_claude` itself.
- Tests must never invoke the real `claude` CLI (slow, costs real usage,
  and won't run in an environment that isn't logged in) - mock
  `subprocess.run` or monkeypatch `backend.agents.run_claude` directly, or
  monkeypatch `backend.api.classify_task_ioms` /
  `backend.api.spawn_canary_instances_for_task` /
  `backend.api.deploy_canary_instance` for routes that depend on them
  (see both test files for examples of each).
- Run `uv run pytest` before considering a backend change done.
