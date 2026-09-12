"""
Minimal authoritative-for-our-domains, recursive-for-everything-else DNS
server. Answers A queries for canary domains (elsa-toys-fake-answers-a1b2c3d4
.canary.test, ...) from a shared zones.json that backend/agents.py updates on
each deploy; forwards every other query upstream unchanged.

Forwarding matters: this resolver becomes the machine's *only* nameserver
(see scripts/mac-dns.sh) while active, so anything not in zones.json - which
is everything except our canary domains - has to keep working normally.
"""

import json
import os
import time
from pathlib import Path

from dnslib import QTYPE, RR, A, DNSRecord
from dnslib.server import BaseResolver, DNSServer

ZONES_FILE = Path(os.environ.get("DNS_ZONES_FILE", "/data/zones.json"))
UPSTREAM = os.environ.get("DNS_UPSTREAM", "8.8.8.8")


def _load_zones() -> dict[str, str]:
    try:
        return json.loads(ZONES_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class CanaryResolver(BaseResolver):
    def resolve(self, request: DNSRecord, handler) -> DNSRecord:
        qname = str(request.q.qname).rstrip(".")
        qtype = QTYPE[request.q.qtype]

        if qtype == "A":
            ip = _load_zones().get(qname)
            if ip:
                reply = request.reply()
                reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(ip), ttl=30))
                return reply

        try:
            response = request.send(UPSTREAM, 53, timeout=3)
            return DNSRecord.parse(response)
        except Exception:
            return request.reply()  # empty reply beats hanging the client


if __name__ == "__main__":
    server = DNSServer(CanaryResolver(), port=53, address="0.0.0.0")
    print(f"dns-resolver listening on :53/udp - zones={ZONES_FILE}, upstream={UPSTREAM}")
    server.start_thread()
    while server.isAlive():
        time.sleep(1)
