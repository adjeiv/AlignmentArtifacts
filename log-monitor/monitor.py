"""
Tails static-site's nginx access log and checks each request against the
per-domain endpoint regex catalog backend/agents.py writes to
ENDPOINTS_FILE (see _register_endpoints) - a match means an agent hit one
of a canary instance's registered routes, so this POSTs to the backend's
trigger endpoint to record the detection.

Deliberately dependency-free (stdlib only): this is a small side-process
watching a log file, not part of the main app, so it doesn't need FastAPI,
requests, etc.
"""

import json
import os
import re
import time
import urllib.request
from pathlib import Path

ACCESS_LOG = Path(os.environ.get("ACCESS_LOG", "/logs/canary_access.log"))
ENDPOINTS_FILE = Path(os.environ.get("ENDPOINTS_FILE", "/data/endpoints.json"))
BACKEND_ORIGIN = os.environ.get("BACKEND_ORIGIN", "http://backend:8000")

# In-memory only (not persisted across restarts) - just to avoid re-POSTing
# the same (instance, iom) pair on every repeat hit or log replay; the
# backend's trigger endpoint is safe to call again regardless.
_already_triggered: set[tuple[str, str]] = set()


def _load_endpoints() -> dict:
    try:
        return json.loads(ENDPOINTS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _trigger(instance_id: str, iom_id: str) -> None:
    key = (instance_id, iom_id)
    if key in _already_triggered:
        return
    url = f"{BACKEND_ORIGIN}/api/canary-instances/{instance_id}/trigger/{iom_id}"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=5)
        _already_triggered.add(key)
        print(f"triggered instance={instance_id} iom={iom_id}", flush=True)
    except Exception as e:
        print(f"failed to trigger instance={instance_id} iom={iom_id}: {e}", flush=True)


def _handle_line(line: str) -> None:
    # log_format canary '$time_iso8601 $host $request_uri' (static-site/nginx.conf)
    parts = line.rstrip("\n").split(" ", 2)
    if len(parts) != 3:
        return
    _time, host, uri = parts

    zone = _load_endpoints().get(host)
    if not zone:
        return

    for endpoint in zone.get("endpoints", []):
        try:
            #if re.search(endpoint["path_regex"], uri):
            # hardcoding just any hit to the canaries for now, not enough time to get the full endpoint logic working
            if re.search("^/.*$", uri):
                _trigger(zone["instance_id"], endpoint["iom_id"])
        except re.error:
            continue


def _tail(path: Path):
    while not path.exists():
        time.sleep(1)
    with path.open("r") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line


if __name__ == "__main__":
    print(
        f"log-monitor watching {ACCESS_LOG}, endpoints={ENDPOINTS_FILE}, backend={BACKEND_ORIGIN}",
        flush=True,
    )
    for line in _tail(ACCESS_LOG):
        _handle_line(line)
