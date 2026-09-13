#!/bin/bash
# Generates a local CA + a wildcard cert for *.canary.test, signed by that CA.
# One cert covers every canary domain (they're all single-label subdomains of
# canary.test) so nginx never needs per-domain certs or a reload on deploy.
#
# Output goes to pki/out/ (gitignored - ca.key is a private key, even for a
# throwaway demo CA it shouldn't be committed). Run once; delete pki/out/ to
# regenerate (e.g. if you want a fresh CA).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/out"
TLD="canary.test"

mkdir -p "$OUT"

if [ -f "$OUT/ca.pem" ]; then
  echo "pki/out/ca.pem already exists - reusing it (delete pki/out/ to also rotate the CA and re-run 'make ca-trust')."
else
  openssl genrsa -out "$OUT/ca.key" 4096
  openssl req -x509 -new -nodes -key "$OUT/ca.key" -sha256 -days 3650 \
    -subj "/O=Alignment Artifacts Local Demo/CN=Alignment Artifacts Local CA" \
    -out "$OUT/ca.pem"
fi

# The leaf (wildcard) cert is regenerated every run, reusing whatever CA is
# on disk - no need to re-trust anything when only this changes.
#
# extendedKeyUsage=serverAuth is not optional: macOS's local/System trust
# store rejects a TLS server cert without it even when its issuing CA is
# fully trusted (silent TLS failures, no useful browser error) - this is
# also why basicConstraints/keyUsage are set explicitly rather than left to
# openssl's defaults, which don't include any of these.
openssl genrsa -out "$OUT/wildcard.key" 2048
openssl req -new -key "$OUT/wildcard.key" \
  -subj "/CN=*.${TLD}" \
  -out "$OUT/wildcard.csr"

cat > "$OUT/wildcard.ext" <<EOF
subjectAltName = DNS:*.${TLD}, DNS:${TLD}
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

openssl x509 -req -in "$OUT/wildcard.csr" -CA "$OUT/ca.pem" -CAkey "$OUT/ca.key" \
  -CAcreateserial -out "$OUT/wildcard.pem" -days 825 -sha256 \
  -extfile "$OUT/wildcard.ext"

rm -f "$OUT/wildcard.csr" "$OUT/wildcard.ext"

# static-site/nginx.conf selects ssl_certificate_key via a variable (so it
# can pick a per-domain key for arbitrary canary domains, not just this
# wildcard) - that makes nginx's unprivileged worker process (not the root
# master, which only pre-loads *static* ssl_certificate_key paths at
# startup) open this file itself, per-connection, for every TLS handshake
# including ones that resolve back to this same wildcard. openssl's default
# 0600 blocks that read. Same tradeoff backend/agents.py's
# _issue_leaf_cert makes for per-canary keys - world-readable, not
# world-writable, and this is a throwaway local demo key regardless.
chmod 644 "$OUT/wildcard.key"

echo "Generated wildcard cert for *.${TLD} (and CA, if it didn't already exist) in pki/out/"
echo "Next: make ca-trust (trusts pki/out/ca.pem system-wide, if not already done), then reload/restart the static-site container."
