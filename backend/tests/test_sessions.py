import pytest

from app.core.presence import presence_manager
from tests.conftest import register_and_login


@pytest.fixture(autouse=True)
def _reset_presence_manager():
    yield
    presence_manager.connections.clear()
    presence_manager.tab_status.clear()


# ── List sessions ────────────────────────────────────────────────────────────


def test_list_sessions_returns_current_active_session(client):
    register_and_login(client, "alice", "alice@test.com")
    r = client.get("/api/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] is not None


# ── is_current flag ──────────────────────────────────────────────────────────


def test_list_sessions_flags_single_session_as_current(client):
    register_and_login(client, "alice", "alice@test.com")
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True


def test_list_sessions_exactly_one_current_with_multiple_sessions(client):
    register_and_login(client, "alice", "alice@test.com")
    # Second login creates a new UserSession row; the cookie jar now
    # holds the newer token, so only the newer row is "current".
    client.post(
        "/api/auth/login",
        json={"email": "alice@test.com", "password": "password123", "persistent": False},
    )
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 2
    current_flags = [s["is_current"] for s in sessions]
    assert current_flags.count(True) == 1
    assert current_flags.count(False) == 1


def test_list_sessions_requires_auth(client):
    r = client.get("/api/sessions")
    assert r.status_code == 401


def test_revoke_session_emits_session_revoked_over_ws(client):
    register_and_login(client, "alice", "alice@test.com")
    sessions = client.get("/api/sessions").json()
    session_id = sessions[0]["id"]

    with client.websocket_connect("/ws?tab_id=tab-A") as ws:
        # Drain the initial presence.bulk frame sent on connect.
        first = ws.receive_json()
        assert first["type"] == "presence.bulk"

        r = client.delete(f"/api/sessions/{session_id}")
        assert r.status_code == 204

        event = ws.receive_json()
        assert event == {"type": "session.revoked", "session_id": session_id}


def test_revoke_session_fans_out_to_all_tabs_of_same_user(client):
    register_and_login(client, "alice", "alice@test.com")
    sessions = client.get("/api/sessions").json()
    session_id = sessions[0]["id"]

    with client.websocket_connect("/ws?tab_id=tab-A") as ws_a, \
            client.websocket_connect("/ws?tab_id=tab-B") as ws_b:
        # Drain initial presence.bulk on both tabs.
        assert ws_a.receive_json()["type"] == "presence.bulk"
        assert ws_b.receive_json()["type"] == "presence.bulk"

        r = client.delete(f"/api/sessions/{session_id}")
        assert r.status_code == 204

        # Both tabs of the same user should receive the event.
        def _next_revoke(ws):
            while True:
                ev = ws.receive_json()
                if ev.get("type") == "session.revoked":
                    return ev

        assert _next_revoke(ws_a) == {"type": "session.revoked", "session_id": session_id}
        assert _next_revoke(ws_b) == {"type": "session.revoked", "session_id": session_id}


def test_revoke_session_targets_only_the_owning_user(client, monkeypatch):
    """Sanity: the emit always targets current_user.id, never another user."""
    import uuid
    captured: list[tuple[uuid.UUID, dict]] = []

    from app.core.presence import presence_manager as pm

    real_send = pm.send_to_user

    async def spy_send(user_id, event):
        captured.append((user_id, event))
        await real_send(user_id, event)

    monkeypatch.setattr(pm, "send_to_user", spy_send)

    register_and_login(client, "alice", "alice@test.com")
    alice_id = client.get("/api/auth/me").json()["id"]
    sessions = client.get("/api/sessions").json()
    session_id = sessions[0]["id"]

    r = client.delete(f"/api/sessions/{session_id}")
    assert r.status_code == 204

    revoke_calls = [
        (uid, ev) for uid, ev in captured if ev.get("type") == "session.revoked"
    ]
    assert len(revoke_calls) == 1
    assert str(revoke_calls[0][0]) == alice_id


def test_list_sessions_excludes_revoked(client):
    register_and_login(client, "alice", "alice@test.com")
    # Logout revokes the session
    client.post("/api/auth/logout")
    # Need fresh auth to call sessions
    client.post("/api/auth/login", json={"email": "alice@test.com", "password": "password123", "persistent": False})
    sessions = client.get("/api/sessions").json()
    # Only the new login session should be active
    assert len(sessions) == 1


def test_list_sessions_returns_multiple_active_sessions(client):
    register_and_login(client, "alice", "alice@test.com")
    # Login again (different "session" — same client in tests, but creates new UserSession row)
    client.post("/api/auth/login", json={"email": "alice@test.com", "password": "password123", "persistent": False})
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert len(r.json()) >= 2


# ── Revoke session ────────────────────────────────────────────────────────────


def test_revoke_session_returns_204(client):
    register_and_login(client, "alice", "alice@test.com")
    sessions = client.get("/api/sessions").json()
    session_id = sessions[0]["id"]
    r = client.delete(f"/api/sessions/{session_id}")
    assert r.status_code == 204


def test_revoke_session_removes_it_from_list(client):
    register_and_login(client, "alice", "alice@test.com")
    # Create a second session
    client.post("/api/auth/login", json={"email": "alice@test.com", "password": "password123", "persistent": False})
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 2

    # Revoke the first one
    session_id = sessions[0]["id"]
    client.delete(f"/api/sessions/{session_id}")

    remaining = client.get("/api/sessions").json()
    ids = [s["id"] for s in remaining]
    assert session_id not in ids


def test_revoke_session_returns_404_for_unknown_id(client):
    register_and_login(client, "alice", "alice@test.com")
    import uuid
    r = client.delete(f"/api/sessions/{uuid.uuid4()}")
    assert r.status_code == 404


def test_revoke_session_cannot_access_other_users_session(client):
    register_and_login(client, "alice", "alice@test.com")
    alice_sessions = client.get("/api/sessions").json()
    alice_session_id = alice_sessions[0]["id"]

    # Register and login as bob
    client.post("/api/auth/register", json={"username": "bob", "email": "bob@test.com", "password": "password123"})
    r = client.delete(f"/api/sessions/{alice_session_id}")
    assert r.status_code == 404


def test_revoke_session_requires_auth(client):
    import uuid
    r = client.delete(f"/api/sessions/{uuid.uuid4()}")
    assert r.status_code == 401
