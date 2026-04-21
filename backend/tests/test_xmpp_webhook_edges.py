"""Edge / negative-path tests for the Prosody webhook (TASK-13 §2.3).

`test_admin_jabber.py` covers the happy paths (token / persist / preview
flag / login + status round-trip). This file fills in:

- logout event drops the session from the registry
- malformed JSON body → 422 (pydantic), does NOT mutate state
- missing `type` discriminator → 422
- unknown `type` value → 422
- federation dashboard on an empty DB returns empty collections
- federation `recent` is capped at 50 rows, newest first
- s2s peer count drops off as expected when the webhook reports logout
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import xmpp_registry
from app.core.config import settings
from app.models.federation import FederationLog

from tests.conftest import register_and_login


_HEADERS = {"X-XMPP-Webhook-Token": "t"}


def _enable_webhook(monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")


def _make_admin(client: TestClient, session: Session, username: str, email: str) -> None:
    from sqlmodel import select

    from app.models.user import User

    register_and_login(client, username, email)
    user = session.exec(select(User).where(User.username == username)).first()
    assert user is not None
    user.is_admin = True
    session.add(user)
    session.commit()


# ── logout flow ─────────────────────────────────────────────────────────────


def test_webhook_logout_removes_session_from_registry(
    client: TestClient, monkeypatch
) -> None:
    _enable_webhook(monkeypatch)
    xmpp_registry._reset_for_tests()
    ts = datetime.now(timezone.utc).isoformat()

    # Login
    r = client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            "type": "session.client",
            "ts": ts,
            "event": "login",
            "jid": "alice@server-a.local",
            "client": "Gajim",
            "ip": "10.0.0.1",
            "session_id": "s-1",
        },
    )
    assert r.status_code == 204
    assert len(xmpp_registry.list_sessions_snapshot()) == 1

    # Logout (same jid+session_id key)
    r = client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            "type": "session.client",
            "ts": ts,
            "event": "logout",
            "jid": "alice@server-a.local",
            "session_id": "s-1",
        },
    )
    assert r.status_code == 204
    assert xmpp_registry.list_sessions_snapshot() == []


# ── malformed / schema-invalid payloads ─────────────────────────────────────


def test_webhook_malformed_json_returns_422(client: TestClient, monkeypatch) -> None:
    _enable_webhook(monkeypatch)
    r = client.post(
        "/api/internal/xmpp/event",
        headers={**_HEADERS, "Content-Type": "application/json"},
        content="{ this is not json",
    )
    assert r.status_code == 422


def test_webhook_missing_type_discriminator_returns_422(
    client: TestClient, monkeypatch
) -> None:
    _enable_webhook(monkeypatch)
    r = client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            # "type" missing
            "ts": datetime.now(timezone.utc).isoformat(),
            "direction": "out",
            "local_jid": "a@server-a.local",
            "remote_jid": "b@server-b.local",
            "remote_server": "server-b.local",
        },
    )
    assert r.status_code == 422


def test_webhook_unknown_type_value_returns_422(client: TestClient, monkeypatch) -> None:
    _enable_webhook(monkeypatch)
    r = client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            "type": "not.a.real.type",
            "ts": datetime.now(timezone.utc).isoformat(),
            "jid": "x@y",
        },
    )
    assert r.status_code == 422


def test_webhook_malformed_does_not_touch_db(
    client: TestClient, session: Session, monkeypatch
) -> None:
    _enable_webhook(monkeypatch)
    # Sanity: table is empty
    assert session.exec(
        __import__("sqlmodel").select(FederationLog)
    ).all() == []

    client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={"type": "federation.message", "ts": "not-a-date",
              "direction": "out", "local_jid": "a@x",
              "remote_jid": "b@y", "remote_server": "y"},
    )
    # Still empty — no partial write.
    assert session.exec(
        __import__("sqlmodel").select(FederationLog)
    ).all() == []


# ── admin federation endpoint edges ─────────────────────────────────────────


def test_federation_endpoint_empty_when_no_rows(
    client: TestClient, session: Session
) -> None:
    _make_admin(client, session, "ivan", "ivan@example.com")
    body = client.get("/api/admin/jabber/federation").json()
    assert body == {"remotes": [], "recent": []}


def test_federation_recent_caps_at_fifty_newest_first(
    client: TestClient, session: Session, monkeypatch
) -> None:
    _enable_webhook(monkeypatch)
    _make_admin(client, session, "ivan", "ivan@example.com")

    # 60 rows across 30 minutes, oldest → newest
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    for i in range(60):
        ts = (base + timedelta(seconds=i * 30)).isoformat()
        r = client.post(
            "/api/internal/xmpp/event",
            headers=_HEADERS,
            json={
                "type": "federation.message",
                "ts": ts,
                "direction": "out",
                "local_jid": "ivan@server-a.local",
                "remote_jid": f"peer-{i}@server-b.local",
                "remote_server": "server-b.local",
                "message_preview": f"msg-{i:02d}",
            },
        )
        assert r.status_code == 204

    body = client.get("/api/admin/jabber/federation").json()
    assert len(body["recent"]) == 50

    # Strict monotonic decrease in ts — newest first
    timestamps = [row["ts"] for row in body["recent"]]
    assert timestamps == sorted(timestamps, reverse=True)

    # The most recent row in the payload is the last one we inserted (msg-59)
    assert body["recent"][0]["preview"] == "msg-59"
    # The oldest in the 50-row window is msg-10 (we dropped msg-00..msg-09)
    assert body["recent"][-1]["preview"] == "msg-10"


def test_federation_remotes_sorted_by_last_active(
    client: TestClient, session: Session, monkeypatch
) -> None:
    _enable_webhook(monkeypatch)
    _make_admin(client, session, "ivan", "ivan@example.com")
    now = datetime.now(timezone.utc)

    # Stale remote (10 min ago)
    client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            "type": "federation.message",
            "ts": (now - timedelta(minutes=10)).isoformat(),
            "direction": "out",
            "local_jid": "ivan@server-a.local",
            "remote_jid": "x@stale.example",
            "remote_server": "stale.example",
        },
    )
    # Fresh remote (just now)
    client.post(
        "/api/internal/xmpp/event",
        headers=_HEADERS,
        json={
            "type": "federation.message",
            "ts": now.isoformat(),
            "direction": "in",
            "local_jid": "ivan@server-a.local",
            "remote_jid": "y@fresh.example",
            "remote_server": "fresh.example",
        },
    )

    body = client.get("/api/admin/jabber/federation").json()
    servers_in_order = [r["server"] for r in body["remotes"]]
    assert servers_in_order == ["fresh.example", "stale.example"]


# ── xmpp_registry direct unit tests ─────────────────────────────────────────


def test_registry_multiple_resources_per_jid():
    """Same JID with different resources must register independently — the
    dashboard should show Gajim and a phone as two separate rows."""
    xmpp_registry._reset_for_tests()
    xmpp_registry.record_login(
        "alice@server-a.local", client="Gajim", ip="10.0.0.1", session_id="s-1"
    )
    xmpp_registry.record_login(
        "alice@server-a.local", client="Conversations", ip="10.0.0.2", session_id="s-2"
    )
    snap = xmpp_registry.list_sessions_snapshot()
    assert len(snap) == 2
    assert {s.client for s in snap} == {"Gajim", "Conversations"}


def test_registry_logout_only_drops_matching_session():
    xmpp_registry._reset_for_tests()
    xmpp_registry.record_login("alice@a", session_id="s-1")
    xmpp_registry.record_login("alice@a", session_id="s-2")
    xmpp_registry.record_logout("alice@a", session_id="s-1")
    snap = xmpp_registry.list_sessions_snapshot()
    assert len(snap) == 1
    assert snap[0].session_id == "s-2"


def test_registry_s2s_peer_tracking():
    xmpp_registry._reset_for_tests()
    assert xmpp_registry.s2s_peer_count() == 0
    xmpp_registry.record_s2s_peer("server-b.local")
    xmpp_registry.record_s2s_peer("server-b.local")  # idempotent
    assert xmpp_registry.s2s_peer_count() == 1
    xmpp_registry.record_s2s_peer("server-c.local")
    assert xmpp_registry.s2s_peer_count() == 2
    xmpp_registry.drop_s2s_peer("server-b.local")
    assert xmpp_registry.s2s_peer_count() == 1
