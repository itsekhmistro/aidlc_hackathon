"""In-memory XMPP session registry — populated by the Prosody webhook (TASK-13).

Lives for the lifetime of the FastAPI process. Not persisted: if the backend
restarts, the dashboard shows empty sessions until Prosody re-emits
``session.client`` events. That is acceptable because Prosody's
``mod_admin_telnet`` equivalent behaves the same — session state is intrinsic
to the server process, and in production we would scrape Prosody directly.

The registry is deliberately simple (a module-level dict) so that unit tests
can import and clear it. No locking because the FastAPI handlers that mutate
it run in the same asyncio loop; if we ever move to multiple workers, this
and its sibling ``s2s_peers`` must move to Redis.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# Cap the response payload so the /status endpoint stays bounded even if
# Prosody pushes thousands of sessions. The UI surfaces a "truncated" badge.
SESSIONS_TRUNCATE_AT = 200


@dataclass
class RegisteredSession:
    jid: str
    client: str | None
    ip: str | None
    session_id: str | None
    connected_at_monotonic: float


_sessions: dict[str, RegisteredSession] = {}
_s2s_peers: set[str] = set()
_process_start_monotonic: float = time.monotonic()


def _key(jid: str, session_id: str | None) -> str:
    # Same JID with different resources (e.g. `alice@x/gajim` + `alice@x/phone`)
    # must each register; use the full JID as the key, fall back to session id.
    return f"{jid}:{session_id or ''}"


def record_login(
    jid: str,
    *,
    client: str | None = None,
    ip: str | None = None,
    session_id: str | None = None,
) -> None:
    _sessions[_key(jid, session_id)] = RegisteredSession(
        jid=jid,
        client=client,
        ip=ip,
        session_id=session_id,
        connected_at_monotonic=time.monotonic(),
    )


def record_logout(jid: str, *, session_id: str | None = None) -> None:
    _sessions.pop(_key(jid, session_id), None)


def record_s2s_peer(server: str) -> None:
    _s2s_peers.add(server)


def drop_s2s_peer(server: str) -> None:
    _s2s_peers.discard(server)


def list_sessions_snapshot() -> list[RegisteredSession]:
    # Stable order by connection age (oldest first) matches the mock in the spec.
    return sorted(_sessions.values(), key=lambda s: s.connected_at_monotonic)


def s2s_peer_count() -> int:
    return len(_s2s_peers)


def get_process_start_monotonic() -> float:
    return _process_start_monotonic


def _reset_for_tests() -> None:
    _sessions.clear()
    _s2s_peers.clear()
