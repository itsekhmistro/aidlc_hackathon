from tests.conftest import register_and_login


# ── List sessions ────────────────────────────────────────────────────────────


def test_list_sessions_returns_current_active_session(client):
    register_and_login(client, "alice", "alice@test.com")
    r = client.get("/api/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] is not None


def test_list_sessions_requires_auth(client):
    r = client.get("/api/sessions")
    assert r.status_code == 401


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
