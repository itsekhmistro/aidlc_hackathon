"""Tests for /api/personal-rooms — display_name resolution."""
from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def _auth(client: TestClient, name: str) -> TestClient:
    return register_and_login(client, name, f"{name}@test.com")


def _login(client: TestClient, name: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={"email": f"{name}@test.com", "password": "password123", "persistent": False},
    )
    assert r.status_code == 200, r.text
    return client


def _me_id(client: TestClient) -> str:
    return client.get("/api/auth/me").json()["id"]


def _befriend(client: TestClient, *, as_user: str, other: str) -> None:
    """Register `other` (if needed), have `as_user` send a request, `other` accept."""
    # alice sends
    _login(client, as_user)
    r = client.post("/api/friends/request", json={"username": other})
    assert r.status_code == 201, r.text
    friendship_id = r.json()["id"]

    # switch to other, accept
    client.cookies.clear()
    _login(client, other)
    r = client.patch(f"/api/friends/{friendship_id}/accept")
    assert r.status_code == 200, r.text


def test_personal_room_exposes_counterpart_username_as_display_name(client: TestClient) -> None:
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "jack")
    _befriend(client, as_user="alice", other="jack")

    # alice opens the DM
    client.cookies.clear()
    _login(client, "alice")
    jack_id = client.get("/api/auth/me")  # alice's /me after switch? No — need jack's id.
    # Grab jack's id via alice's contacts list.
    friends = client.get("/api/friends").json()
    jack_id = [
        f["addressee_id"] if f["requester_id"] == _me_id(client) else f["requester_id"]
        for f in friends
    ][0]

    resp = client.get(f"/api/personal-rooms/{jack_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_personal"] is True
    # Canonical name is still the deterministic `__dm__:…:…` key.
    assert body["name"].startswith("__dm__:")
    # Display name from alice's viewpoint is "jack".
    assert body["display_name"] == "jack"


def test_personal_room_display_name_flips_for_each_viewer(client: TestClient) -> None:
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "jack")
    _befriend(client, as_user="alice", other="jack")

    # alice POV
    client.cookies.clear()
    _login(client, "alice")
    alice_id = _me_id(client)
    friends = client.get("/api/friends").json()
    jack_id = next(
        f["addressee_id"] if f["requester_id"] == alice_id else f["requester_id"]
        for f in friends
    )
    room_alice = client.get(f"/api/personal-rooms/{jack_id}").json()
    assert room_alice["display_name"] == "jack"

    # jack POV on the same room — via /api/rooms/mine
    client.cookies.clear()
    _login(client, "jack")
    mine = client.get("/api/rooms/mine").json()
    dm_rows = [r for r in mine if r["is_personal"]]
    assert len(dm_rows) == 1
    assert dm_rows[0]["id"] == room_alice["id"]
    assert dm_rows[0]["display_name"] == "alice"


def test_personal_room_post_message_after_ban_returns_403(client: TestClient) -> None:
    """After a ban, posting to an existing personal room returns 403 (spec 04.5 + 06.10)."""
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "jack")
    _befriend(client, as_user="alice", other="jack")

    client.cookies.clear()
    _login(client, "alice")
    alice_id = _me_id(client)
    friends = client.get("/api/friends").json()
    jack_id = next(
        f["addressee_id"] if f["requester_id"] == alice_id else f["requester_id"]
        for f in friends
    )
    room = client.get(f"/api/personal-rooms/{jack_id}").json()
    room_id = room["id"]

    # Seed one message BEFORE the ban so we can later verify history is preserved.
    r = client.post(f"/api/rooms/{room_id}/messages", json={"content": "Hi jack!"})
    assert r.status_code == 201, r.text

    # Alice bans jack.
    r_ban = client.post("/api/bans", json={"banned_id": jack_id})
    assert r_ban.status_code == 201, r_ban.text

    # Alice can no longer post in the personal room.
    r_post = client.post(f"/api/rooms/{room_id}/messages", json={"content": "still there?"})
    assert r_post.status_code == 403, r_post.text
    assert "ban" in r_post.json()["detail"].lower()

    # Jack (the banned party) also cannot post — ban blocks both directions.
    client.cookies.clear()
    _login(client, "jack")
    r_post_jack = client.post(f"/api/rooms/{room_id}/messages", json={"content": "yo"})
    assert r_post_jack.status_code == 403, r_post_jack.text


def test_personal_room_history_preserved_after_ban(client: TestClient) -> None:
    """After a ban, historical messages remain visible (spec 04.6)."""
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "jack")
    _befriend(client, as_user="alice", other="jack")

    client.cookies.clear()
    _login(client, "alice")
    alice_id = _me_id(client)
    friends = client.get("/api/friends").json()
    jack_id = next(
        f["addressee_id"] if f["requester_id"] == alice_id else f["requester_id"]
        for f in friends
    )
    room = client.get(f"/api/personal-rooms/{jack_id}").json()
    room_id = room["id"]

    r = client.post(f"/api/rooms/{room_id}/messages", json={"content": "historical message"})
    assert r.status_code == 201, r.text

    # Alice bans jack.
    client.post("/api/bans", json={"banned_id": jack_id})

    # Alice can still list history.
    r_list = client.get(f"/api/rooms/{room_id}/messages")
    assert r_list.status_code == 200, r_list.text
    msgs = r_list.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["content"] == "historical message"

    # Jack can still list history too.
    client.cookies.clear()
    _login(client, "jack")
    r_list_jack = client.get(f"/api/rooms/{room_id}/messages")
    assert r_list_jack.status_code == 200, r_list_jack.text
    assert len(r_list_jack.json()["messages"]) == 1


def test_personal_room_edit_message_after_ban_returns_403(client: TestClient) -> None:
    """After a ban, editing a message in a personal room returns 403 (spec 04.5 + 06.10)."""
    _auth(client, "alice")
    client.cookies.clear()
    _auth(client, "jack")
    _befriend(client, as_user="alice", other="jack")

    client.cookies.clear()
    _login(client, "alice")
    alice_id = _me_id(client)
    friends = client.get("/api/friends").json()
    jack_id = next(
        f["addressee_id"] if f["requester_id"] == alice_id else f["requester_id"]
        for f in friends
    )
    room = client.get(f"/api/personal-rooms/{jack_id}").json()
    room_id = room["id"]

    r = client.post(f"/api/rooms/{room_id}/messages", json={"content": "original"})
    assert r.status_code == 201, r.text
    message_id = r.json()["id"]

    # Alice bans jack.
    client.post("/api/bans", json={"banned_id": jack_id})

    # Alice can no longer edit her own message in the DM room.
    r_edit = client.patch(
        f"/api/rooms/{room_id}/messages/{message_id}",
        json={"content": "edited"},
    )
    assert r_edit.status_code == 403, r_edit.text
    assert "ban" in r_edit.json()["detail"].lower()


def test_non_personal_room_display_name_equals_name(client: TestClient) -> None:
    _auth(client, "alice")
    r = client.post("/api/rooms", json={"name": "general", "visibility": "public"})
    assert r.status_code == 201, r.text
    room = r.json()
    assert room["is_personal"] is False
    assert room["display_name"] == "general"
    assert room["name"] == "general"

    # Regular room lookup also carries display_name == name.
    got = client.get(f"/api/rooms/{room['id']}").json()
    assert got["display_name"] == "general"
