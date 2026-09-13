#!/usr/bin/env python3
"""Live-tails canary trigger events for one task.

Usage:
    uv run python scripts/monitor_canaries.py <task_id> [--backend-url URL]
        [--interval SECONDS] [--all]

Fetches GET /api/tasks/{task_id}/canary-instances once - that instance set
is fixed at task-creation time (spawn_canary_instances_for_task runs
synchronously; only each instance's deploy is backgrounded, per
backend/agents.py) - then repeatedly polls each instance's
GET /api/canary-instances/{id}/events and prints any event not already
printed, in timestamp order. Prints TRIGGER-level events by default (an
IOM detection - see backend/api.py's trigger_canary_instance_route); pass
--all to also see info/warning/error events (deploy heartbeats etc).
"""
from __future__ import annotations

import argparse
import sys
import time

import requests


def fetch(url: str):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id", help="Task id to monitor, e.g. from POST /api/companies/{id}/tasks")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds (default: 2)")
    parser.add_argument("--all", action="store_true", help="Show every event, not just TRIGGER-level")
    args = parser.parse_args()

    base = args.backend_url.rstrip("/")

    try:
        task = fetch(f"{base}/api/tasks/{args.task_id}")
    except requests.exceptions.ConnectionError:
        print(f"error: could not reach backend at {base} - is `make backend` (or `make up`) running?", file=sys.stderr)
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"error: task {args.task_id!r} not found ({e.response.status_code})", file=sys.stderr)
        return 1

    instances = fetch(f"{base}/api/tasks/{args.task_id}/canary-instances")
    if not instances:
        print(f"task {args.task_id!r} ({task['prompt']!r}) has no canary instances - nothing to monitor.")
        return 0

    ioms = {iom["id"]: iom["name"] for iom in fetch(f"{base}/api/ioms")}
    canary_types = {ct["id"]: ct["name"] for ct in fetch(f"{base}/api/canary-types")}
    instances_by_id = {ci["id"]: ci for ci in instances}

    print(f"Monitoring task {args.task_id!r} ({task['prompt']!r}) - {len(instances)} canary instance(s):")
    for ci in instances:
        ct_name = canary_types.get(ci["canary_type_id"], "?")
        iom_names = ", ".join(ioms.get(i, i) for i in ci["iom_ids"]) or "-"
        print(f"  - {ci['name']} ({ci['id']}) [{ct_name}] iom(s): {iom_names}")
    print("Ctrl+C to stop.\n")

    seen: set[str] = set()
    try:
        while True:
            batch = []
            for ci in instances:
                try:
                    events = fetch(f"{base}/api/canary-instances/{ci['id']}/events")
                except requests.exceptions.RequestException:
                    continue
                for e in events:
                    if e["id"] in seen:
                        continue
                    if args.all or e["level"] == "trigger":
                        batch.append(e)
                    seen.add(e["id"])

            batch.sort(key=lambda e: e["timestamp"])
            for e in batch:
                ci = instances_by_id.get(e["canary_instance_id"], {})
                name = ci.get("name", "?")
                if e.get("iom_id"):
                    iom_label = f"{ioms.get(e['iom_id'], e['iom_id'])} ({e['iom_id']})"
                else:
                    iom_label = "-"
                tag = "TRIGGER" if e["level"] == "trigger" else e["level"].upper()
                print(
                    f"[{e['timestamp']}] {tag:7} instance={name} ({e['canary_instance_id']}) "
                    f"iom={iom_label} :: {e['message']}"
                )
                sys.stdout.flush()

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
