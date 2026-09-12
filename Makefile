.PHONY: install up backend frontend test ca-generate ca-trust ca-untrust dns-use dns-restore

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
