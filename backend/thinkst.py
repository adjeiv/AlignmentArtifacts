"""
Thinkst Canarytokens integration: real, third-party-monitored credentials
via canarytokens.org's free public API (see
https://github.com/thinkst/canarytokens).

Kept as its own module (mirroring backend/github_canary.py's shape) since
two independent canary subsystems plant Thinkst credentials:
backend/agents.py's deploy_static_site (a fake .env) and
backend/github_canary.py's issue/comment seeding. backend/agents.py imports
from backend/github_canary.py, so this had to move out from under
backend/agents.py to avoid a circular import.

log-monitor/ only catches *inbound* hits on our own nginx. A leaked AWS key
or webhook URL is used *outbound* - against AWS's real API, or by fetching
a URL Thinkst controls - so detecting that needs a different mechanism:
poll_thinkst_tokens_once (started from backend/api.py's app lifespan)
periodically asks canarytokens.org whether a planted token has fired.

Opt-in: THINKST_ALERT_EMAIL must be set (some email you actually control -
Thinkst requires an email or webhook per token, even though we only ever
poll /history ourselves and never rely on that channel firing). Unset means
create_canarytoken always returns None, so every caller's planting attempt
quietly no-ops, same as backend/agents.py's deploy_noop default.

run_thinkst_poller takes a `trigger` callable (backend.agents's
trigger_canary_instance) as a parameter rather than importing it directly,
for the same circular-import reason as backend/github_canary.py's poller.
"""

import asyncio
import os
from typing import Any, Callable

import requests

from backend.models import CanaryInstance

THINKST_BASE_URL = os.environ.get("THINKST_BASE_URL", "https://canarytokens.org")
THINKST_ALERT_EMAIL = os.environ.get("THINKST_ALERT_EMAIL")
THINKST_POLL_INTERVAL_SECONDS = int(os.environ.get("THINKST_POLL_INTERVAL_SECONDS", "30"))

_thinkst_tokens: list[dict[str, Any]] = []
_thinkst_tokens_lock = asyncio.Lock()


def create_canarytoken(kind: str, memo: str) -> dict[str, Any] | None:
    if not THINKST_ALERT_EMAIL:
        return None
    try:
        resp = requests.post(
            f"{THINKST_BASE_URL}/generate",
            json={"token_type": kind, "memo": memo, "email": THINKST_ALERT_EMAIL},
            timeout=10,
        )
        resp.raise_for_status()
        token_response = resp.json()
    except requests.RequestException:
        return None
    if token_response.get("error"):
        return None
    return token_response


async def register_token(token: str, auth: str, instance_id: str, iom_id: str) -> None:
    """Records a created token for poll_thinkst_tokens_once. Called by both
    backend/agents.py (.env credentials) and backend/github_canary.py
    (issue/comment-seeded credentials) after create_canarytoken succeeds."""
    async with _thinkst_tokens_lock:
        _thinkst_tokens.append(
            {"token": token, "auth": auth, "instance_id": instance_id, "iom_id": iom_id, "reported": False}
        )


def _check_thinkst_history(token: str, auth: str) -> bool:
    try:
        resp = requests.get(
            f"{THINKST_BASE_URL}/history", params={"token": token, "auth": auth}, timeout=10
        )
        resp.raise_for_status()
        return bool(resp.json().get("history", {}).get("hits"))
    except requests.RequestException:
        return False


async def poll_thinkst_tokens_once(
    canary_instances: list[CanaryInstance], trigger: Callable[[CanaryInstance, str], None]
) -> None:
    """Checks every not-yet-reported Thinkst token's /history for a hit
    (credential actually used, not just planted) and triggers its canary
    instance if so. Called on a loop from backend/api.py's app lifespan."""
    async with _thinkst_tokens_lock:
        pending = [t for t in _thinkst_tokens if not t["reported"]]

    for entry in pending:
        fired = await asyncio.to_thread(_check_thinkst_history, entry["token"], entry["auth"])
        if not fired:
            continue
        instance = next((ci for ci in canary_instances if ci.id == entry["instance_id"]), None)
        if instance is not None:
            trigger(instance, entry["iom_id"])
        entry["reported"] = True


async def run_thinkst_poller(
    canary_instances: list[CanaryInstance], trigger: Callable[[CanaryInstance, str], None]
) -> None:
    if not THINKST_ALERT_EMAIL:
        return
    while True:
        await asyncio.sleep(THINKST_POLL_INTERVAL_SECONDS)
        await poll_thinkst_tokens_once(canary_instances, trigger)
