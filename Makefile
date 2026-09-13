.PHONY: install up backend frontend test monitor cheatsheet ca-generate ca-trust ca-untrust dns-use dns-restore

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

# Live-tails canary trigger events for one task: `make monitor <task-id>`.
# Requires the backend to be running (`make backend` / `make up`). The task
# id is a positional arg, not TASK=... - the catch-all `%:` rule below
# swallows it so make doesn't also treat it as a target name.
monitor:
	@uv run python scripts/monitor_canaries.py $(filter-out $@,$(MAKECMDGOALS))

# Writes /tmp/extra_assets from one task's deployed canaries: `make
# cheatsheet <task-id>` (see testing/README.md). Requires the backend to be
# running. Same positional-arg trick as `monitor` above.
cheatsheet:
	@uv run python scripts/cheatsheet.py $(filter-out $@,$(MAKECMDGOALS))

# Automated benchmark runner: `make benchmark` (every testing/*.md scenario)
# or `make benchmark 01_exam_benchmark_cheating` for just one. Requires the
# backend to be running; see scripts/run_benchmark.py --help for --repeats,
# --fixtures-dir, --agent-model, etc.
benchmark:
	@uv run python scripts/run_benchmark.py $(filter-out $@,$(MAKECMDGOALS))

# Generates ./fixtures/<scenario_id>/ task environments for `make benchmark
# --fixtures-dir fixtures` (see testing/README.md). No backend needed - calls
# `claude` directly via backend/agents.py's run_claude. Skips scenarios that
# already have a fixtures/ subdir - run scripts/generate_fixtures.py directly
# (not through this target) for --force/--model/other flags, since make's
# positional-arg trick here only forwards scenario ids, not flags.
fixtures:
	@uv run python scripts/generate_fixtures.py $(filter-out $@,$(MAKECMDGOALS))

%:
	@:

# --- Canary domains: nginx + DNS resolver + local CA (docker compose only) ---
# See README.md "Custom domains for canaries" for the full picture and order
# of operations (generate -> trust -> compose up -> dns-use -> ... -> restore).

# One-time: generates pki/out/ca.pem + wildcard.pem for *.canary.test.
ca-generate:
	./pki/generate.sh

# macOS only. Trusts pki/out/ca.pem system-wide (System keychain) so browsers
# accept the wildcard cert nginx presents for *.canary.test over HTTPS.
# Requires sudo. Skip this and canary sites still work over plain HTTP.
ca-trust:
	sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain pki/out/ca.pem

# Undoes ca-trust.
ca-untrust:
	sudo security remove-trusted-cert -d pki/out/ca.pem

# macOS only. Points this Mac's DNS at the dns-resolver container (127.0.0.1)
# so *.canary.test resolves - everything else still forwards upstream (see
# dns-resolver/resolver.py). Requires `docker compose up` to already be
# running, and sudo (networksetup). Always pair with `make dns-restore` when
# done, or this machine loses DNS the moment the containers stop.
dns-use:
	./scripts/mac-dns.sh use

# Undoes dns-use - restores the normal DHCP-provided DNS.
dns-restore:
	./scripts/mac-dns.sh restore
