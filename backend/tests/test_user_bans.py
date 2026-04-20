"""Unit tests for /api/bans — TASK-04."""
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
    return register_and_login(client, name, f"{name}@test.com")


def _login(client: TestClient, name: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={"email": f"{name}@test.com", "password": "password123", "persistent": False},
    )
    assert r.status_code == 200, f"login as {name} failed: {r.text}"
    return client


def _get_user_id(client: TestClient, username: str) -> str:
    """Register a new user and return their user id."""
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@test.com", "password": "password123"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ─── POST /api/bans ───────────────────────────────────────────────────────────


def test_ban_user_returns_201(client: TestClient):
    _auth(client, "banner1")
    banned_id = _get_user_id(client, "banned1")
    client.cookies.clear()
    _login(client, "banner1")
    r = client.post("/api/bans", json={"banned_id": banned_id})
    assert r.status_code == 201
    data = r.json()
    assert data["banned_id"] == banned_id
    assert "banner_id" in data
    assert "created_at" in data


def test_ban_emits_user_banned_with_both_ids(client: TestClient):
    """Payload must carry BOTH banner_id and banned_id (WsUserBanned type)."""
    _auth(client, "banneruser")
    banner_id = client.get("/api/auth/me").json()["id"]
    client.cookies.clear()
    _auth(client, "targetuser")
    target_id = client.get("/api/auth/me").json()["id"]

    # Target opens a WS, banner then issues the ban.
    with client.websocket_connect("/ws?tab_id=target-tab") as ws:
        assert ws.receive_json()["type"] == "presence.bulk"

        client.cookies.clear()
        _login(client, "banneruser")
        r = client.post("/api/bans", json={"banned_id": target_id})
        assert r.status_code == 201

        # Skip any presence-related frames that may race in.
        seen = None
        for _ in range(5):
            ev = ws.receive_json()
            if ev.get("type") == "user.banned":
                seen = ev
                break
        assert seen is not None, "user.banned frame never arrived"
        assert seen["banner_id"] == banner_id
        assert seen["banned_id"] == target_id


def test_ban_yourself_returns_400(client: TestClient):
    r_reg = client.post(
        "/api/auth/register",
        json={"username": "selfseal", "email": "selfseal@test.com", "password": "password123"},
    )
    assert r_reg.status_code == 201
    my_id = r_reg.json()["id"]
    r = client.post("/api/bans", json={"banned_id": my_id})
    assert r.status_code == 400
    assert "yourself" in r.json()["detail"].lower()


def test_ban_duplicate_returns_409(client: TestClient):
    _auth(client, "banner2")
    banned_id = _get_user_id(client, "banned2")
    client.cookies.clear()
    _login(client, "banner2")
    client.post("/api/bans", json={"banned_id": banned_id})
    r = client.post("/api/bans", json={"banned_id": banned_id})
    assert r.status_code == 409


def test_ban_unauthenticated_returns_401(client: TestClient):
    r = client.post("/api/bans", json={"banned_id": str(uuid.uuid4())})
    assert r.status_code == 401


def test_ban_removes_existing_friendship(client: TestClient):
    """When user A bans user B, any existing friendship/request should be removed."""
    _auth(client, "friendA")
    client.cookies.clear()
    _auth(client, "friendB")
    client.cookies.clear()

    # friendA sends a friend request to friendB
    _login(client, "friendA")
    req_r = client.post("/api/friends/request", json={"username": "friendB"})
    assert req_r.status_code == 201
    # addressee_id is friendB's id
    friendB_id_str = req_r.json()["addressee_id"]

    # friendA now bans friendB — should remove the pending friendship
    r = client.post("/api/bans", json={"banned_id": friendB_id_str})
    assert r.status_code == 201

    # friendB should no longer see an incoming request
    client.cookies.clear()
    _login(client, "friendB")
    incoming_after = client.get("/api/friends/requests/incoming").json()
    assert len(incoming_after) == 0


def test_ban_also_removes_accepted_friendship(client: TestClient):
    """Ban after an accepted friendship removes the friendship record."""
    _auth(client, "banpre1")
    client.cookies.clear()
    _auth(client, "banpre2")
    client.cookies.clear()
    _login(client, "banpre1")
    r_req = client.post("/api/friends/request", json={"username": "banpre2"})
    friendship_id = r_req.json()["id"]
    requester_id = r_req.json()["requester_id"]

    client.cookies.clear()
    _login(client, "banpre2")
    client.patch(f"/api/friends/{friendship_id}/accept")
    # banpre2 now has 1 friend
    assert len(client.get("/api/friends").json()) == 1

    # banpre2 bans banpre1
    r_ban = client.post("/api/bans", json={"banned_id": requester_id})
    assert r_ban.status_code == 201

    # friendship should be removed
    assert len(client.get("/api/friends").json()) == 0


# ─── GET /api/bans ────────────────────────────────────────────────────────────


def test_list_bans_returns_my_bans(client: TestClient):
    _auth(client, "banner3")
    banned_id = _get_user_id(client, "banned3")
    client.cookies.clear()
    _login(client, "banner3")
    client.post("/api/bans", json={"banned_id": banned_id})
    r = client.get("/api/bans")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["banned_id"] == banned_id


def test_list_bans_empty_when_none(client: TestClient):
    _auth(client, "noBans")
    r = client.get("/api/bans")
    assert r.status_code == 200
    assert r.json() == []


def test_list_bans_unauthenticated_returns_401(client: TestClient):
    r = client.get("/api/bans")
    assert r.status_code == 401


# ─── DELETE /api/bans/{banned_id} ────────────────────────────────────────────


def test_unban_user_returns_204(client: TestClient):
    _auth(client, "banner4")
    banned_id = _get_user_id(client, "banned4")
    client.cookies.clear()
    _login(client, "banner4")
    client.post("/api/bans", json={"banned_id": banned_id})
    r = client.delete(f"/api/bans/{banned_id}")
    assert r.status_code == 204


def test_unban_not_found_returns_404(client: TestClient):
    _auth(client, "banner5")
    r = client.delete(f"/api/bans/{uuid.uuid4()}")
    assert r.status_code == 404


def test_unban_by_non_banner_returns_404(client: TestClient):
    """Another user cannot unban someone else's ban (gets 404 since it's not their ban)."""
    _auth(client, "banner6")
    banned_id = _get_user_id(client, "banned6")
    client.cookies.clear()
    _login(client, "banner6")
    client.post("/api/bans", json={"banned_id": banned_id})

    client.cookies.clear()
    _auth(client, "outsider6")
    # outsider6 tries to unban — route filters by current user's bans, so returns 404
    r = client.delete(f"/api/bans/{banned_id}")
    assert r.status_code == 404
