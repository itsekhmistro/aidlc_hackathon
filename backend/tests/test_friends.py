"""Unit tests for /api/friends — TASK-04."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.presence import presence_manager
from tests.conftest import register_and_login


@pytest.fixture(autouse=True)
def _reset_presence_manager():
    yield
    presence_manager.connections.clear()
    presence_manager.tab_status.clear()


# ─── helpers ─────────────────────────────────────────────────────────────────


def _auth(client: TestClient, name: str) -> TestClient:
    """Register user and return authenticated client."""
    return register_and_login(client, name, f"{name}@test.com")


def _login(client: TestClient, name: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={"email": f"{name}@test.com", "password": "password123", "persistent": False},
    )
    assert r.status_code == 200, f"login as {name} failed: {r.text}"
    return client


def _send_request(client: TestClient, to_username: str, msg: str | None = None) -> dict:
    body: dict = {"username": to_username}
    if msg is not None:
        body["message"] = msg
    r = client.post("/api/friends/request", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ─── POST /api/friends/request ────────────────────────────────────────────────


def test_send_friend_request_returns_201(client: TestClient):
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "bob")
    client.cookies.clear()
    _login(client, "alice")
    r = client.post("/api/friends/request", json={"username": "bob"})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["requester_username"] == "alice"
    assert data["addressee_username"] == "bob"
    assert "id" in data


def test_send_friend_request_to_self_returns_400(client: TestClient):
    _auth(client, "charlie")
    r = client.post("/api/friends/request", json={"username": "charlie"})
    assert r.status_code == 400
    assert "yourself" in r.json()["detail"].lower()


def test_send_friend_request_duplicate_returns_409(client: TestClient):
    _auth(client, "dana")
    client.cookies.clear()
    _auth(client, "eve")
    client.cookies.clear()
    _login(client, "dana")
    client.post("/api/friends/request", json={"username": "eve"})
    r = client.post("/api/friends/request", json={"username": "eve"})
    assert r.status_code == 409


def test_send_friend_request_unauthenticated_returns_401(client: TestClient):
    r = client.post("/api/friends/request", json={"username": "nobody"})
    assert r.status_code == 401


def test_send_friend_request_user_not_found_returns_404(client: TestClient):
    _auth(client, "frank")
    r = client.post("/api/friends/request", json={"username": "ghost_xyz_999"})
    assert r.status_code == 404


# ─── GET /api/friends ─────────────────────────────────────────────────────────


def test_list_friends_empty_initially(client: TestClient):
    _auth(client, "grace")
    r = client.get("/api/friends")
    assert r.status_code == 200
    assert r.json() == []


def test_list_friends_populated_after_accept(client: TestClient):
    _auth(client, "henry")
    client.cookies.clear()
    _auth(client, "iris")
    client.cookies.clear()
    _login(client, "henry")
    friendship = _send_request(client, "iris")

    client.cookies.clear()
    _login(client, "iris")
    r = client.patch(f"/api/friends/{friendship['id']}/accept")
    assert r.status_code == 200

    friends = client.get("/api/friends").json()
    assert len(friends) == 1
    assert friends[0]["status"] == "accepted"


def test_list_friends_unauthenticated_returns_401(client: TestClient):
    r = client.get("/api/friends")
    assert r.status_code == 401


# ─── GET /api/friends/requests/incoming ──────────────────────────────────────


def test_incoming_requests_returns_pending_to_me(client: TestClient):
    _auth(client, "jack")
    client.cookies.clear()
    _auth(client, "kate")
    client.cookies.clear()
    _login(client, "jack")
    _send_request(client, "kate")

    client.cookies.clear()
    _login(client, "kate")
    r = client.get("/api/friends/requests/incoming")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["addressee_username"] == "kate"
    assert data[0]["requester_username"] == "jack"
    assert data[0]["status"] == "pending"


def test_incoming_requests_empty_when_none(client: TestClient):
    _auth(client, "liam")
    r = client.get("/api/friends/requests/incoming")
    assert r.status_code == 200
    assert r.json() == []


# ─── PATCH /api/friends/{id}/accept ──────────────────────────────────────────


def test_accept_friend_request_happy_path(client: TestClient):
    _auth(client, "mike")
    client.cookies.clear()
    _auth(client, "nina")
    client.cookies.clear()
    _login(client, "mike")
    friendship = _send_request(client, "nina")

    client.cookies.clear()
    _login(client, "nina")
    r = client.patch(f"/api/friends/{friendship['id']}/accept")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "accepted"


def test_accept_friend_request_emits_friend_accepted_to_requester(client: TestClient):
    """Regression: backend used to emit 'friend.request_accepted' — frontend
    typed 'friend.accepted'. Ensure the renamed event reaches the requester."""
    _auth(client, "xander")
    client.cookies.clear()
    _auth(client, "yara")
    client.cookies.clear()
    _login(client, "xander")
    friendship = _send_request(client, "yara")

    with client.websocket_connect("/ws?tab_id=xander-tab") as ws:
        # Drain initial presence.bulk frame.
        assert ws.receive_json()["type"] == "presence.bulk"

        # Switch to yara and accept the request.
        client.cookies.clear()
        _login(client, "yara")
        r = client.patch(f"/api/friends/{friendship['id']}/accept")
        assert r.status_code == 200

        # Skip non-friend frames (presence.update can race in).
        seen = None
        for _ in range(5):
            ev = ws.receive_json()
            if ev.get("type", "").startswith("friend."):
                seen = ev
                break
        assert seen is not None, "no friend.* event arrived"
        assert seen["type"] == "friend.accepted"
        assert "friendship" in seen


def test_accept_own_request_returns_403(client: TestClient):
    """The requester cannot accept their own friend request."""
    _auth(client, "oscar")
    client.cookies.clear()
    _auth(client, "paula")
    client.cookies.clear()
    _login(client, "oscar")
    friendship = _send_request(client, "paula")

    # Oscar (the requester) tries to accept — should be forbidden
    r = client.patch(f"/api/friends/{friendship['id']}/accept")
    assert r.status_code == 403


def test_accept_nonexistent_friendship_returns_404(client: TestClient):
    _auth(client, "quinn")
    r = client.patch(f"/api/friends/{uuid.uuid4()}/accept")
    assert r.status_code == 404


# ─── DELETE /api/friends/{id} ────────────────────────────────────────────────


def test_delete_friendship_returns_204(client: TestClient):
    _auth(client, "rosa")
    client.cookies.clear()
    _auth(client, "sam")
    client.cookies.clear()
    _login(client, "rosa")
    friendship = _send_request(client, "sam")

    r = client.delete(f"/api/friends/{friendship['id']}")
    assert r.status_code == 204


def test_delete_friendship_as_addressee_returns_204(client: TestClient):
    """Addressee should also be allowed to delete the friendship."""
    _auth(client, "tara")
    client.cookies.clear()
    _auth(client, "uma")
    client.cookies.clear()
    _login(client, "tara")
    friendship = _send_request(client, "uma")

    client.cookies.clear()
    _login(client, "uma")
    r = client.delete(f"/api/friends/{friendship['id']}")
    assert r.status_code == 204


def test_delete_friendship_by_non_participant_returns_403(client: TestClient):
    _auth(client, "victor")
    client.cookies.clear()
    _auth(client, "wendy")
    client.cookies.clear()
    _auth(client, "xander")
    client.cookies.clear()
    _login(client, "victor")
    friendship = _send_request(client, "wendy")

    client.cookies.clear()
    _login(client, "xander")
    r = client.delete(f"/api/friends/{friendship['id']}")
    assert r.status_code == 403


def test_delete_friendship_not_found_returns_404(client: TestClient):
    _auth(client, "yara")
    r = client.delete(f"/api/friends/{uuid.uuid4()}")
    assert r.status_code == 404
