#!/usr/bin/env python3
"""XMPP federation load test — TASK-13 §Load Test.

Runs 50 clients on server A and 50 on server B (configurable), each sending
one message/sec to a paired client on the other server. Measures delivery
latency (round-trip between send → server B's echo), loss, and throughput.

Requires the two-server topology to be up:
    docker compose -f docker-compose.federation.yml up --build

And the accounts pre-provisioned on each Prosody (via FastAPI register, which
the bridge mirrors to Prosody automatically).

Run with:
    uv run python scripts/federation_load_test.py
    uv run python scripts/federation_load_test.py --clients 10 --duration 30

Design notes:
- We use slixmpp (asyncio-native) rather than aioxmpp — same capability, one
  order of magnitude less boilerplate for a throwaway harness.
- Each client is its own slixmpp.ClientXMPP, all under a single asyncio loop.
  With 100 clients and modest per-client memory we stay well under macOS's
  default fd cap, but TASK-16's `ulimit -n 8192` note applies here too if the
  harness ever scales past a few hundred clients.
- Latency is measured end-to-end: client A records monotonic time before
  send; client B, on receive, echoes a timestamp payload back; client A then
  computes RTT on the echo. Missing echoes count as loss.
- This script deliberately does NOT provision accounts. Register them through
  the FastAPI side beforehand (the bridge will mirror to Prosody). If the
  script can't log in it prints a clear error and exits.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import statistics
import sys
import time
from dataclasses import dataclass, field

try:
    from slixmpp import ClientXMPP  # type: ignore[import-not-found]
except ImportError:
    print(
        "slixmpp is not installed. Run:\n"
        "    uv run --with slixmpp python scripts/federation_load_test.py\n"
        "or add slixmpp to the backend dev deps.",
        file=sys.stderr,
    )
    sys.exit(2)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fedload")


@dataclass
class Metrics:
    sent: int = 0
    delivered: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def lost(self) -> int:
        return self.sent - self.delivered

    def summary(self) -> str:
        if not self.latencies_ms:
            return f"sent={self.sent} delivered=0 lost={self.lost} (no latency data)"
        lats = sorted(self.latencies_ms)
        return (
            f"sent={self.sent} delivered={self.delivered} lost={self.lost} "
            f"avg={statistics.mean(lats):.1f}ms "
            f"p95={lats[int(0.95 * len(lats)) - 1]:.1f}ms "
            f"p99={lats[int(0.99 * len(lats)) - 1]:.1f}ms"
        )


class Peer(ClientXMPP):
    """One simulated XMPP user under load.

    Two roles rolled into one class: every peer both sends and receives. The
    sender sets a `Peer.outbox` with (target_jid, payload, send_time_ns) and
    dispatches; the receiver, on incoming message, either echoes the payload
    (for first-hop sends from the OTHER server) or records RTT (for echoes
    coming back from peers of the same server).
    """

    ECHO_PREFIX = "LOAD "

    def __init__(self, jid: str, password: str, metrics: Metrics, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(jid, password)
        self.pending: dict[str, float] = {}  # payload id -> send_time_monotonic
        self.metrics = metrics
        self.loop = loop
        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.register_plugin("xep_0030")  # service discovery
        self.register_plugin("xep_0199")  # XMPP Ping

    async def _on_session_start(self, _event) -> None:
        self.send_presence()
        try:
            await self.get_roster()
        except Exception:
            pass  # rosters are optional for the load path

    def _on_message(self, msg) -> None:
        if msg["type"] not in ("chat", "normal"):
            return
        body = str(msg["body"])
        if not body.startswith(self.ECHO_PREFIX):
            return
        # Two possibilities:
        # 1) we're the receiver of a fresh probe → echo back as "ECHO <id>"
        # 2) we're the sender getting our echo back → compute RTT
        parts = body.split(" ", 2)
        if len(parts) < 2:
            return
        kind = parts[1]
        if kind == "PROBE" and len(parts) == 3:
            payload_id = parts[2]
            self.send_message(
                mto=str(msg["from"]),
                mbody=f"{self.ECHO_PREFIX}ECHO {payload_id}",
                mtype="chat",
            )
            return
        if kind == "ECHO" and len(parts) == 3:
            payload_id = parts[2]
            t0 = self.pending.pop(payload_id, None)
            if t0 is None:
                return
            latency_ms = (time.monotonic() - t0) * 1000.0
            self.metrics.delivered += 1
            self.metrics.latencies_ms.append(latency_ms)

    def send_probe(self, target_jid: str) -> None:
        payload_id = f"{self.boundjid.bare}-{random.randint(0, 1 << 62):x}"
        self.pending[payload_id] = time.monotonic()
        self.metrics.sent += 1
        self.send_message(
            mto=target_jid,
            mbody=f"{self.ECHO_PREFIX}PROBE {payload_id}",
            mtype="chat",
        )


async def _connect(peer: Peer, host: str, port: int) -> bool:
    peer.connect((host, port), disable_starttls=True, use_ssl=False)
    # slixmpp exposes `.wait_until()` in newer releases; for broad compat we
    # poll the `session_bind_event` flag.
    for _ in range(40):
        if peer.session_bind_event.is_set():
            return True
        await asyncio.sleep(0.25)
    return False


async def run_server_side(
    server_label: str,
    host: str,
    port: int,
    domain: str,
    users: list[tuple[str, str]],
    targets: list[str],
    duration_s: int,
    rate_per_client: float,
    metrics: Metrics,
) -> None:
    loop = asyncio.get_event_loop()
    peers: list[Peer] = []
    for username, password in users:
        peer = Peer(f"{username}@{domain}", password, metrics, loop)
        ok = await _connect(peer, host, port)
        if not ok:
            log.error("[%s] %s failed to bind", server_label, username)
            continue
        peers.append(peer)
    log.warning("[%s] %d peers online", server_label, len(peers))

    t_end = time.monotonic() + duration_s
    interval = 1.0 / rate_per_client
    while time.monotonic() < t_end:
        for peer in peers:
            target = random.choice(targets)
            try:
                peer.send_probe(target)
            except Exception as exc:
                log.warning("send error: %s", exc)
        await asyncio.sleep(interval)

    for peer in peers:
        peer.disconnect()


async def amain(args: argparse.Namespace) -> int:
    m_a = Metrics()
    m_b = Metrics()

    users_a = [(f"{args.prefix}a{i}", args.password) for i in range(args.clients)]
    users_b = [(f"{args.prefix}b{i}", args.password) for i in range(args.clients)]
    targets_on_b = [f"{u}@{args.domain_b}" for u, _ in users_b]
    targets_on_a = [f"{u}@{args.domain_a}" for u, _ in users_a]

    start = time.monotonic()
    await asyncio.gather(
        run_server_side(
            "A",
            args.host_a,
            args.port_a,
            args.domain_a,
            users_a,
            targets_on_b,
            args.duration,
            args.rate,
            m_a,
        ),
        run_server_side(
            "B",
            args.host_b,
            args.port_b,
            args.domain_b,
            users_b,
            targets_on_a,
            args.duration,
            args.rate,
            m_b,
        ),
    )
    elapsed = time.monotonic() - start

    total_sent = m_a.sent + m_b.sent
    total_delivered = m_a.delivered + m_b.delivered

    print()
    print("────── Federation load test ──────")
    print(f"Clients A: {args.clients} | Clients B: {args.clients}")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Messages sent: {total_sent} | Delivered: {total_delivered} | Lost: {total_sent - total_delivered}")
    combined = m_a.latencies_ms + m_b.latencies_ms
    if combined:
        combined.sort()
        print(
            f"Avg latency: {statistics.mean(combined):.1f}ms | "
            f"p95: {combined[int(0.95 * len(combined)) - 1]:.1f}ms | "
            f"p99: {combined[int(0.99 * len(combined)) - 1]:.1f}ms"
        )
    throughput = total_sent / elapsed if elapsed > 0 else 0.0
    print(f"Throughput: {throughput:.1f} msg/s")
    print()
    print(f"A→B: {m_a.summary()}")
    print(f"B→A: {m_b.summary()}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TASK-13 XMPP federation load test")
    p.add_argument("--clients", type=int, default=50, help="clients per server (default 50)")
    p.add_argument("--duration", type=int, default=120, help="test length in seconds (default 120)")
    p.add_argument("--rate", type=float, default=1.0, help="messages per client per second (default 1)")
    p.add_argument("--host-a", default="localhost")
    p.add_argument("--port-a", type=int, default=5222)
    p.add_argument("--domain-a", default="server-a.local")
    p.add_argument("--host-b", default="localhost")
    p.add_argument("--port-b", type=int, default=5322)
    p.add_argument("--domain-b", default="server-b.local")
    p.add_argument("--prefix", default="load_", help="username prefix — must match pre-provisioned users")
    p.add_argument("--password", default="loadtest-password")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        raise SystemExit(asyncio.run(amain(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)
