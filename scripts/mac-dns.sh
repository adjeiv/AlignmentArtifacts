#!/bin/bash
# Points this Mac's DNS at our local resolver (127.0.0.1, published by the
# dns-resolver container - see docker-compose.yml) so canary *.canary.test
# domains resolve, or restores the normal DHCP-provided DNS.
#
# Does both networksetup (what most apps' getaddrinfo() honors on macOS) and
# a direct /etc/resolv.conf write (some tools read that file directly,
# bypassing the system resolver config) - belt and suspenders. Note macOS's
# configd can regenerate /etc/resolv.conf on its own after a network change,
# silently undoing the direct write; re-run `make dns-use` if that happens.
#
# If a browser still won't resolve *.canary.test after this: check whether
# it has "Secure DNS" / DNS-over-HTTPS enabled (on by default in current
# Chrome/Firefox/Safari) - DoH talks straight to a remote resolver over
# HTTPS and ignores the system resolver entirely, so neither of this
# script's changes can reach it. Turn it off (or add an exception) to test.
set -euo pipefail

RESOLV_CONF="/etc/resolv.conf"
RESOLV_BACKUP="/etc/resolv.conf.pre-canary-dns"

active_service() {
  local iface
  iface=$(route get default 2>/dev/null | awk '/interface: /{print $2}')
  if [ -z "$iface" ]; then
    return 1
  fi
  networksetup -listnetworkserviceorder \
    | grep -B1 "Device: $iface)" \
    | head -n1 \
    | sed -E 's/^\([0-9]+\) //'
}

cmd="${1:-}"
service="$(active_service || true)"

if [ -z "$service" ]; then
  echo "Could not detect the active network service (Wi-Fi/Ethernet)." >&2
  echo "Set it manually: sudo networksetup -setdnsservers \"<Service>\" 127.0.0.1" >&2
  exit 1
fi

case "$cmd" in
  use)
    echo "Active network service: $service"
    echo "Pointing its DNS at 127.0.0.1 (our resolver - make sure 'docker compose up' / the dns-resolver container is running)"
    sudo networksetup -setdnsservers "$service" 127.0.0.1

    if [ ! -f "$RESOLV_BACKUP" ]; then
      sudo cp "$RESOLV_CONF" "$RESOLV_BACKUP" 2>/dev/null || echo "(no existing $RESOLV_CONF to back up)"
    fi
    echo "Also writing $RESOLV_CONF directly"
    printf 'nameserver 127.0.0.1\n' | sudo tee "$RESOLV_CONF" >/dev/null

    echo
    echo "If *.canary.test still doesn't resolve in a browser, check its Secure DNS / DNS-over-HTTPS setting (see header of this script) - that bypasses both changes above entirely."
    ;;
  restore)
    echo "Active network service: $service"
    echo "Restoring DHCP-provided DNS"
    sudo networksetup -setdnsservers "$service" empty

    if [ -f "$RESOLV_BACKUP" ]; then
      sudo mv "$RESOLV_BACKUP" "$RESOLV_CONF"
      echo "Restored $RESOLV_CONF from backup"
    else
      echo "No backup of $RESOLV_CONF found - leaving it as-is (macOS regenerates it automatically on network changes anyway)"
    fi
    ;;
  *)
    echo "usage: $0 {use|restore}" >&2
    exit 1
    ;;
esac
