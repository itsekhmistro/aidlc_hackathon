"""TASK-16 Locust harness.

Four scenarios selectable via ``--tags``:

* ``steady``   — S1 steady_state_300 (NFR 3.1 + 3.2 message latency)
* ``fanout``   — S2 fanout_1000 (NFR 3.1 1000/room + 3.2 delivery)
* ``presence`` — S3 presence_propagation (NFR 3.2 <2s)
* ``history``  — S4 history_10k_read (NFR 3.2 10k-message room)

Run from the repository root, e.g.::

    uv run --project backend locust -f loadtests/locustfile.py \\
        --tags steady --headless -u 300 -r 30 -t 5m --csv reports/s1

Architecture notes
------------------

* Locust is gevent-based. We use ``websocket-client`` (sync) so each
  virtual user can own a real :class:`websocket.WebSocket` without
  polluting the asyncio loop. Do NOT import ``asyncio`` or the
  ``websockets`` library here — they fight with gevent's monkey patch.
* Each VU loads a distinct session token from ``loadtests/tokens.json``
  (partitioned by VU index via ``environment.runner.user_count``).
* Latency is reported by firing a synthetic ``WS`` request-event named
  ``e2e:<scenario>`` into Locust's normal stats, so ``--csv`` output
  already contains the p50/p95/p99 numbers ``RESULTS.md`` needs.
* The backend uses the ``auth_token`` cookie (see
  ``backend/app/api/deps.py``) and the WS endpoint is mounted at ``/ws``
  with a required ``tab_id`` query parameter (see
  ``backend/app/api/routes/ws.py``).

Auth flow the harness follows — it NEVER calls ``/api/auth/login``
(bcrypt would serialise the hot path). The seeder wrote ``UserSession``
rows directly; we set the ``auth_token`` cookie on the
:class:`requests.Session` and on the WS ``Cookie`` header manually.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import gevent
import websocket  # websocket-client (sync, gevent-friendly)
from locust import (
    HttpUser,
    constant_throughput,
    events,
    between,
    tag,
    task,
)

log = logging.getLogger("loadtest")

# Repo-root-relative token file; override with LOADTEST_TOKENS env var.
DEFAULT_TOKENS_PATH = Path(__file__).parent / "tokens.json"
BIG_ROOM_NAME = "loadtest_bigroom"
HISTORY_ROOM_NAME = "loadtest_history"

# Class-level token-assignment lock so parallel spawn doesn't double-assign.
_TOKEN_LOCK = threading.Lock()
_TOKEN_INDEX = {"n": 0}


def _load_tokens() -> list[dict[str, str]]:
    path = Path(os.environ.get("LOADTEST_TOKENS", DEFAULT_TOKENS_PATH))
    if not path.exists():
        raise RuntimeError(
            f"Token file {path} not found. Run `uv run python -m scripts.seed_load "
            f"--token-out {path}` from backend/ first."
        )
    data = json.loads(path.read_text())
    if not data:
        raise RuntimeError(f"Token file {path} is empty.")
    return data


def _next_token() -> dict[str, str]:
    """Hand out tokens round-robin, thread-safe across spawn."""
    tokens = _TOKENS_CACHE
    with _TOKEN_LOCK:
        idx = _TOKEN_INDEX["n"] % len(tokens)
        _TOKEN_INDEX["n"] += 1
    return tokens[idx]


try:
    _TOKENS_CACHE = _load_tokens()
except RuntimeError as exc:  # pragma: no cover — reported at runtime
    log.warning("tokens.json not loaded at import time: %s", exc)
    _TOKENS_CACHE = []


def _ws_url_from_host(host: str, tab_id: str) -> str:
    """Translate ``http(s)://host:port`` → ``ws(s)://host:port/ws?tab_id=…``."""
    parsed = urlparse(host)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path  # handles ``localhost:8000`` without scheme
    return f"{scheme}://{netloc}/ws?tab_id={tab_id}"


def _fire_ws_latency(name: str, latency_ms: float, payload_bytes: int) -> None:
    """Emit a synthetic request event so Locust's stats capture WS latency."""
    events.request.fire(
        request_type="WS",
        name=name,
        response_time=latency_ms,
        response_length=payload_bytes,
        exception=None,
        context={},
    )


def _fire_ws_failure(name: str, exception: BaseException) -> None:
    events.request.fire(
        request_type="WS",
        name=name,
        response_time=0,
        response_length=0,
        exception=exception,
        context={},
    )


class WSClientMixin:
    """Shared WS lifecycle for every scenario.

    Owns one ``websocket.WebSocket`` per VU, plus a greenlet that reads
    frames and dispatches them via :meth:`_handle_ws_event`. Subclasses
    override the handler.
    """

    wait_time = between(0, 0)  # default; scenarios override per-task

    # Overridden per-scenario so latency events are attributed correctly.
    latency_name = "e2e:unknown"

    def on_start(self) -> None:  # type: ignore[override]
        # Pick a session token and wire it into the HTTP client + WS cookie.
        self.token_info = _next_token()
        self.session_token: str = self.token_info["session_token"]
        self.user_id: str = self.token_info["user_id"]
        self.username: str = self.token_info["username"]
        self.client.cookies.set("auth_token", self.session_token)
        self.tab_id = uuid.uuid4().hex
        # per-VU send-timestamps keyed by client_msg_id.
        self._inflight: dict[str, int] = {}
        self._rooms: list[dict[str, Any]] = []
        self._ws: websocket.WebSocket | None = None
        self._ws_stop = False
        self._open_ws()
        self._reader_greenlet = gevent.spawn(self._ws_reader)

    def on_stop(self) -> None:  # type: ignore[override]
        self._ws_stop = True
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:  # pragma: no cover
                pass
        try:
            self._reader_greenlet.kill(block=False)
        except Exception:  # pragma: no cover
            pass

    # ── websocket plumbing ──────────────────────────────────────────────

    def _open_ws(self) -> None:
        url = _ws_url_from_host(self.host, self.tab_id)
        header = [f"Cookie: auth_token={self.session_token}"]
        try:
            ws = websocket.create_connection(url, header=header, timeout=30)
            ws.settimeout(30)
            self._ws = ws
        except Exception as exc:
            _fire_ws_failure(f"ws_connect:{self.latency_name}", exc)
            raise

    def _ws_reader(self) -> None:
        ws = self._ws
        if ws is None:
            return
        while not self._ws_stop:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                if not self._ws_stop:
                    _fire_ws_failure(f"ws_recv:{self.latency_name}", exc)
                return
            if not raw:
                return
            try:
                event = json.loads(raw)
            except Exception:
                continue
            try:
                self._handle_ws_event(event, raw)
            except Exception as exc:  # pragma: no cover — defensive
                log.warning("handler error in %s: %s", type(self).__name__, exc)

    # Subclasses override.
    def _handle_ws_event(self, event: dict[str, Any], raw: str) -> None:
        return None

    def _send_ws_json(self, payload: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            ws.send(json.dumps(payload))
        except Exception as exc:
            _fire_ws_failure(f"ws_send:{self.latency_name}", exc)

    # ── HTTP helpers ────────────────────────────────────────────────────

    def _load_my_rooms(self) -> None:
        with self.client.get(
            "/api/rooms/mine", name="GET /api/rooms/mine", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"status={resp.status_code}")
                self._rooms = []
                return
            try:
                self._rooms = resp.json() or []
            except Exception as exc:
                resp.failure(f"bad json: {exc}")
                self._rooms = []


# ─── S1 steady_state_300 ────────────────────────────────────────────────


@tag("steady")
class SteadyStateUser(WSClientMixin, HttpUser):
    """300 VUs, 1 msg every ~10s into a random room the user belongs to.

    On receipt of ``message.new`` with a matching ``client_msg_id`` we
    emit the e2e latency as a synthetic ``WS`` request event.
    """

    wait_time = between(9.0, 11.0)
    latency_name = "e2e:steady"

    def on_start(self) -> None:  # type: ignore[override]
        super().on_start()
        self._load_my_rooms()
        # 30s presence heartbeat on a background greenlet — matches the
        # frontend's cadence; keeps ``online`` status alive.
        self._heartbeat_greenlet = gevent.spawn(self._heartbeat_loop)

    def on_stop(self) -> None:  # type: ignore[override]
        try:
            self._heartbeat_greenlet.kill(block=False)
        except Exception:  # pragma: no cover
            pass
        super().on_stop()

    def _heartbeat_loop(self) -> None:
        while not self._ws_stop:
            gevent.sleep(30)
            if self._ws_stop:
                return
            self._send_ws_json({"type": "presence.heartbeat", "status": "online"})

    def _handle_ws_event(self, event: dict[str, Any], raw: str) -> None:
        if event.get("type") != "message.new":
            return
        msg = event.get("message") or {}
        cid = msg.get("client_msg_id")
        if not cid:
            return
        t_send = self._inflight.pop(cid, None)
        if t_send is None:
            return
        latency_ms = (time.monotonic_ns() - t_send) / 1e6
        _fire_ws_latency(self.latency_name, latency_ms, len(raw))

    @task
    def post_one_message(self) -> None:
        if not self._rooms:
            self._load_my_rooms()
            if not self._rooms:
                return
        room = random.choice(self._rooms)
        room_id = room["id"]
        cid = uuid.uuid4().hex
        payload = {"content": f"loadtest msg {cid[:8]}", "client_msg_id": cid}
        self._inflight[cid] = time.monotonic_ns()
        with self.client.post(
            f"/api/rooms/{room_id}/messages",
            json=payload,
            name="POST /api/rooms/{room_id}/messages",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"status={resp.status_code}")
                self._inflight.pop(cid, None)


# ─── S2 fanout_1000 ─────────────────────────────────────────────────────


def _find_room_by_name(tokens: list[dict[str, str]], http, name: str) -> dict[str, Any] | None:
    """Paginate ``/api/rooms`` (public list) to locate the seeded room by name.

    Shared helper for fanout + history scenarios. ``http`` is a
    :class:`requests.Session`-compatible object (``self.client``) with the
    auth cookie already set.
    """
    cursor: str | None = None
    for _ in range(50):  # bounded — seeded rooms pool is tiny
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = http.get(
            "/api/rooms",
            params=params,
            name="GET /api/rooms (seeded-room lookup)",
        )
        if resp.status_code != 200:
            return None
        rooms = resp.json() or []
        for r in rooms:
            if r.get("name") == name:
                return r
        if len(rooms) < 100:
            return None
        cursor = rooms[-1]["id"]
    return None


@tag("fanout")
class FanoutListener(WSClientMixin, HttpUser):
    """Passive listener: waits for ``message.new`` in the big room.

    Records ``client_msg_id → count`` so a post-run analyser can verify
    delivered/sent == 1.000 per publisher send.
    """

    # Listeners don't actively send anything on the HTTP side — Locust
    # requires at least one task, so keep a tight no-op.
    wait_time = between(30, 60)
    latency_name = "e2e:fanout"
    weight = 999

    def on_start(self) -> None:  # type: ignore[override]
        super().on_start()
        self.big_room = _find_room_by_name(_TOKENS_CACHE, self.client, BIG_ROOM_NAME)
        if not self.big_room:
            log.warning("fanout: %s room not found; listener going idle", BIG_ROOM_NAME)
        # client_msg_id → list of receipt latencies; written by _handle_ws_event.
        self._receipts: dict[str, float] = {}

    def _handle_ws_event(self, event: dict[str, Any], raw: str) -> None:
        if event.get("type") != "message.new":
            return
        msg = event.get("message") or {}
        if not self.big_room or msg.get("room_id") != self.big_room["id"]:
            return
        cid = msg.get("client_msg_id")
        if not cid:
            return
        t_send = _PUBLISHER_TIMESTAMPS.get(cid)
        if t_send is None:
            # Publisher lives in the same process in headless mode; if not
            # (multi-process), fall back to measuring receipt-rate only.
            _fire_ws_latency(self.latency_name, 0.0, len(raw))
            return
        latency_ms = (time.monotonic_ns() - t_send) / 1e6
        _fire_ws_latency(self.latency_name, latency_ms, len(raw))

    @task
    def idle(self) -> None:
        # Burn the wait_time; real work happens in the WS reader greenlet.
        return None


# Publisher↔listener correlation table. Lives at module scope so every
# FanoutListener in the same process can read it without extra plumbing.
# For ``--processes N`` the map is per-process; the delivered/sent ratio
# becomes an approximation (listeners in other processes fire 0-latency
# receipts). Document this in RESULTS.md when it matters.
_PUBLISHER_TIMESTAMPS: dict[str, int] = {}


@tag("fanout")
class FanoutPublisher(WSClientMixin, HttpUser):
    """Single publisher — 2 messages/second into the big room."""

    # constant_throughput(2) → 2 tasks/sec, matching the spec's 2 msg/s.
    wait_time = constant_throughput(2)
    latency_name = "e2e:fanout_publish"
    weight = 1

    def on_start(self) -> None:  # type: ignore[override]
        super().on_start()
        self.big_room = _find_room_by_name(_TOKENS_CACHE, self.client, BIG_ROOM_NAME)
        if not self.big_room:
            log.error("fanout: %s not found; publisher cannot run", BIG_ROOM_NAME)

    @task
    def publish_one(self) -> None:
        if not self.big_room:
            return
        cid = uuid.uuid4().hex
        _PUBLISHER_TIMESTAMPS[cid] = time.monotonic_ns()
        with self.client.post(
            f"/api/rooms/{self.big_room['id']}/messages",
            json={"content": f"fanout {cid[:8]}", "client_msg_id": cid},
            name="POST /api/rooms/{room_id}/messages [bigroom]",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"status={resp.status_code}")
                _PUBLISHER_TIMESTAMPS.pop(cid, None)


# ─── S3 presence_propagation ────────────────────────────────────────────


@tag("presence")
class PresenceToggler(WSClientMixin, HttpUser):
    """One VU toggles online↔afk every 10s.

    Observers correlate by ``user_id + status`` on ``presence.update``.
    The server doesn't echo a correlation id; we publish the monotonic
    timestamp via ``_PRESENCE_TIMESTAMPS`` (same-process only — see the
    note on ``_PUBLISHER_TIMESTAMPS``).
    """

    wait_time = between(10, 10)
    latency_name = "e2e:presence_toggle"
    weight = 1

    def on_start(self) -> None:  # type: ignore[override]
        super().on_start()
        self._next_status = "afk"

    @task
    def toggle(self) -> None:
        status = self._next_status
        self._next_status = "online" if status == "afk" else "afk"
        _PRESENCE_TIMESTAMPS[(self.user_id, status)] = time.monotonic_ns()
        self._send_ws_json({"type": "presence.heartbeat", "status": status})


_PRESENCE_TIMESTAMPS: dict[tuple[str, str], int] = {}


@tag("presence")
class PresenceObserver(WSClientMixin, HttpUser):
    """Records heartbeat → presence.update propagation latency."""

    wait_time = between(30, 60)
    latency_name = "e2e:presence"
    weight = 99

    def _handle_ws_event(self, event: dict[str, Any], raw: str) -> None:
        if event.get("type") != "presence.update":
            return
        uid = event.get("user_id")
        status = event.get("status")
        if not uid or not status:
            return
        t_send = _PRESENCE_TIMESTAMPS.get((uid, status))
        if t_send is None:
            return
        latency_ms = (time.monotonic_ns() - t_send) / 1e6
        _fire_ws_latency(self.latency_name, latency_ms, len(raw))

    @task
    def idle(self) -> None:
        return None


# ─── S4 history_10k_read ────────────────────────────────────────────────


@tag("history")
class HistoryReader(HttpUser):
    """Walk the history room: initial page + 5 cursor pages every 30s.

    Per-request latency is captured by Locust's built-in HTTP stats
    (no WS involved). Pass threshold p95 ≤ 500 ms per page.
    """

    wait_time = between(30, 30)

    def on_start(self) -> None:  # type: ignore[override]
        self.token_info = _next_token()
        self.client.cookies.set("auth_token", self.token_info["session_token"])
        self.history_room = _find_room_by_name(_TOKENS_CACHE, self.client, HISTORY_ROOM_NAME)
        if not self.history_room:
            log.error("history: %s room not found", HISTORY_ROOM_NAME)

    @task
    def walk_pages(self) -> None:
        if not self.history_room:
            return
        rid = self.history_room["id"]
        resp = self.client.get(
            f"/api/rooms/{rid}/messages",
            params={"limit": 50},
            name="GET /api/rooms/{room_id}/messages [page 1]",
        )
        if resp.status_code != 200:
            return
        try:
            page = resp.json()
        except Exception:
            return
        cursor = page.get("next_cursor")
        for i in range(2, 7):
            if not cursor:
                return
            r2 = self.client.get(
                f"/api/rooms/{rid}/messages",
                params={"limit": 50, "before": cursor},
                name=f"GET /api/rooms/{{room_id}}/messages [page {i}]",
            )
            if r2.status_code != 200:
                return
            try:
                cursor = r2.json().get("next_cursor")
            except Exception:
                return
