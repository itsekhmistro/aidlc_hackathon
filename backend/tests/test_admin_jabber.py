"""Integration tests for the admin Jabber routes + Prosody webhook (TASK-13)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core import xmpp_registry
from app.core.config import settings
from app.models.user import User

from tests.conftest import register_and_login


def _make_admin(client: TestClient, session: Session, username: str, email: str) -> None:
    register_and_login(client, username, email)
    user = session.exec(select(User).where(User.username == username)).first()
    assert user is not None
    user.is_admin = True
    session.add(user)
    session.commit()


def test_non_admin_gets_403_on_status(client: TestClient) -> None:
    register_and_login(client, "bob", "bob@example.com")
    r = client.get("/api/admin/jabber/status")
    assert r.status_code == 403, r.text


def test_non_admin_gets_403_on_federation(client: TestClient) -> None:
    register_and_login(client, "bob", "bob@example.com")
    r = client.get("/api/admin/jabber/federation")
    assert r.status_code == 403


def test_unauthenticated_gets_401(client: TestClient) -> None:
    r = client.get("/api/admin/jabber/status")
    assert r.status_code == 401


def test_admin_status_returns_shape(client: TestClient, session: Session) -> None:
    xmpp_registry._reset_for_tests()
    _make_admin(client, session, "ivan", "ivan@example.com")
    r = client.get("/api/admin/jabber/status")
    assert r.status_code == 200, r.text
    body = r.json()
    # Exact shape from specs/13-jabber-design.md §2.1
    for key in (
        "server_host",
        "uptime_seconds",
        "connected_clients",
        "s2s_links_active",
        "sessions",
        "truncated",
    ):
        assert key in body
    assert body["connected_clients"] == 0
    assert body["s2s_links_active"] == 0
    assert body["sessions"] == []
    assert body["truncated"] is False


def test_me_includes_is_admin_flag(client: TestClient, session: Session) -> None:
    register_and_login(client, "bob", "bob@example.com")
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["is_admin"] is False

    # Promote and recheck
    user = session.exec(select(User).where(User.username == "bob")).first()
    assert user is not None
    user.is_admin = True
    session.add(user)
    session.commit()

    r = client.get("/api/auth/me")
    assert r.json()["is_admin"] is True


# ── webhook ──────────────────────────────────────────────────────────────────


def test_webhook_requires_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "expected-token")
    payload = {
        "type": "federation.message",
        "ts": datetime.now(timezone.utc).isoformat(),
        "direction": "out",
        "local_jid": "alice@server-a.local",
        "remote_jid": "bob@server-b.local",
        "remote_server": "server-b.local",
    }
    # No header at all
    r = client.post("/api/internal/xmpp/event", json=payload)
    assert r.status_code == 401
    # Wrong header
    r = client.post(
        "/api/internal/xmpp/event",
        json=payload,
        headers={"X-XMPP-Webhook-Token": "wrong"},
    )
    assert r.status_code == 401


def test_webhook_disabled_when_secret_empty(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "")
    payload = {
        "type": "session.client",
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "login",
        "jid": "alice@server-a.local",
    }
    r = client.post(
        "/api/internal/xmpp/event",
        json=payload,
        headers={"X-XMPP-Webhook-Token": "anything"},
    )
    assert r.status_code == 401


def test_webhook_persists_federation_log(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")
    monkeypatch.setattr(settings, "XMPP_LOG_PREVIEWS", True)
    xmpp_registry._reset_for_tests()

    ts = datetime.now(timezone.utc)
    r = client.post(
        "/api/internal/xmpp/event",
        json={
            "type": "federation.message",
            "ts": ts.isoformat(),
            "direction": "out",
            "local_jid": "alice@server-a.local",
            "remote_jid": "bob@server-b.local",
            "remote_server": "server-b.local",
            "message_preview": "hi there",
            "session_id": "s-42",
        },
        headers={"X-XMPP-Webhook-Token": "t"},
    )
    assert r.status_code == 204, r.text

    from app.models.federation import FederationLog

    rows = session.exec(select(FederationLog)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.direction == "out"
    assert row.local_jid == "alice@server-a.local"
    assert row.remote_jid == "bob@server-b.local"
    assert row.remote_server == "server-b.local"
    assert row.message_preview == "hi there"
    assert row.session_id == "s-42"
    # S2S peer should be registered as a side-effect.
    assert xmpp_registry.s2s_peer_count() == 1


def test_webhook_preview_suppression_respects_flag(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")
    monkeypatch.setattr(settings, "XMPP_LOG_PREVIEWS", False)

    r = client.post(
        "/api/internal/xmpp/event",
        json={
            "type": "federation.message",
            "ts": datetime.now(timezone.utc).isoformat(),
            "direction": "in",
            "local_jid": "a@server-a.local",
            "remote_jid": "b@server-b.local",
            "remote_server": "server-b.local",
            "message_preview": "body body body",
        },
        headers={"X-XMPP-Webhook-Token": "t"},
    )
    assert r.status_code == 204

    from app.models.federation import FederationLog

    row = session.exec(select(FederationLog).order_by(FederationLog.ts.desc())).first()
    assert row is not None
    assert row.message_preview is None


def test_webhook_session_login_populates_registry(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")
    xmpp_registry._reset_for_tests()

    r = client.post(
        "/api/internal/xmpp/event",
        json={
            "type": "session.client",
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "login",
            "jid": "alice@server-a.local",
            "client": "Gajim 1.8",
            "ip": "192.168.1.5",
            "session_id": "sess-1",
        },
        headers={"X-XMPP-Webhook-Token": "t"},
    )
    assert r.status_code == 204
    snap = xmpp_registry.list_sessions_snapshot()
    assert len(snap) == 1
    assert snap[0].jid == "alice@server-a.local"
    assert snap[0].client == "Gajim 1.8"


def test_admin_status_reports_registry(client: TestClient, session: Session, monkeypatch) -> None:
    """End-to-end: webhook pushes a login, admin /status surfaces it."""
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")
    xmpp_registry._reset_for_tests()
    _make_admin(client, session, "ivan", "ivan@example.com")

    client.post(
        "/api/internal/xmpp/event",
        json={
            "type": "session.client",
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "login",
            "jid": "alice@server-a.local",
            "client": "Pidgin",
            "ip": "10.0.0.5",
        },
        headers={"X-XMPP-Webhook-Token": "t"},
    )

    body = client.get("/api/admin/jabber/status").json()
    assert body["connected_clients"] == 1
    assert body["sessions"][0]["jid"] == "alice@server-a.local"
    assert body["sessions"][0]["client"] == "Pidgin"


def test_admin_federation_aggregates_rows(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "XMPP_WEBHOOK_TOKEN", "t")
    _make_admin(client, session, "ivan", "ivan@example.com")

    for direction in ("out", "in", "out"):
        client.post(
            "/api/internal/xmpp/event",
            json={
                "type": "federation.message",
                "ts": datetime.now(timezone.utc).isoformat(),
                "direction": direction,
                "local_jid": "alice@server-a.local",
                "remote_jid": "bob@server-b.local",
                "remote_server": "server-b.local",
                "message_preview": f"msg-{direction}",
            },
            headers={"X-XMPP-Webhook-Token": "t"},
        )

    body = client.get("/api/admin/jabber/federation").json()
    assert len(body["remotes"]) == 1
    remote = body["remotes"][0]
    assert remote["server"] == "server-b.local"
    assert remote["direction"] == "both"
    assert remote["message_count"] == 3
    assert len(body["recent"]) == 3
