"""Unit tests for /api/unread — TASK-08."""
import uuid

import pytest
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


def _create_room(client: TestClient, name: str, visibility: str = "public") -> dict:
    r = client.post("/api/rooms", json={"name": name, "visibility": visibility})
    assert r.status_code == 201, r.text
    return r.json()


def _send(client: TestClient, room_id: str, content: str) -> dict:
    r = client.post(f"/api/rooms/{room_id}/messages", json={"content": content})
    assert r.status_code == 201, r.text
    return r.json()


# ─── GET /api/unread ─────────────────────────────────────────────────────────


def test_get_unread_returns_empty_counts_for_user_with_no_rooms(client: TestClient):
    _auth(client, "unr_empty")
    r = client.get("/api/unread")
    assert r.status_code == 200
    assert r.json() == {"counts": {}}


def test_get_unread_returns_zero_for_room_with_no_receipt(client: TestClient):
    """A freshly-joined room has no receipt → counts as 0 (not message count)."""
    _auth(client, "unr_owner1")
    room = _create_room(client, "unr-zero-room")
    _send(client, room["id"], "hi")
    r = client.get("/api/unread")
    assert r.status_code == 200
    # Owner gets 0 because no receipt has been written yet
    assert r.json()["counts"] == {room["id"]: 0}


def test_get_unread_counts_messages_after_receipt(client: TestClient):
    """After mark-read + new messages, unread count increases."""
    _auth(client, "unr_owner2")
    room = _create_room(client, "unr-cnt-room", visibility="public")
    _send(client, room["id"], "before")

    # Second user joins and marks-read
    client.cookies.clear()
    _auth(client, "unr_reader")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.post(f"/api/unread/{room['id']}/mark-read")
    assert r.status_code == 204

    # Owner sends 3 more messages
    client.cookies.clear()
    _login(client, "unr_owner2")
    for i in range(3):
        _send(client, room["id"], f"new {i}")

    # Reader checks unread
    client.cookies.clear()
    _login(client, "unr_reader")
    r = client.get("/api/unread")
    assert r.status_code == 200
    assert r.json()["counts"][room["id"]] == 3


def test_get_unread_unauthenticated_returns_401(client: TestClient):
    r = client.get("/api/unread")
    assert r.status_code == 401


# ─── POST /api/unread/{room_id}/mark-read ────────────────────────────────────


def test_mark_read_happy_path_returns_204(client: TestClient):
    _auth(client, "unr_mk1")
    room = _create_room(client, "unr-mk-room")
    _send(client, room["id"], "msg")
    r = client.post(f"/api/unread/{room['id']}/mark-read")
    assert r.status_code == 204


def test_mark_read_sets_unread_to_zero(client: TestClient):
    _auth(client, "unr_mk_owner")
    room = _create_room(client, "unr-mk-zero-room", visibility="public")
    _send(client, room["id"], "a")
    _send(client, room["id"], "b")

    client.cookies.clear()
    _auth(client, "unr_mk_reader")
    client.post(f"/api/rooms/{room['id']}/join")

    # Baseline: owner's 2 messages exist, no receipt yet → 0
    r = client.get("/api/unread")
    assert r.json()["counts"][room["id"]] == 0

    # Owner posts more
    client.cookies.clear()
    _login(client, "unr_mk_owner")
    _send(client, room["id"], "c")

    # Mark read as reader
    client.cookies.clear()
    _login(client, "unr_mk_reader")
    client.post(f"/api/unread/{room['id']}/mark-read")
    r = client.get("/api/unread")
    assert r.json()["counts"][room["id"]] == 0


def test_mark_read_non_member_returns_403(client: TestClient):
    _auth(client, "unr_mk_owner2")
    room = _create_room(client, "unr-mk-403-room", visibility="private")
    client.cookies.clear()
    _auth(client, "unr_mk_outsider")
    r = client.post(f"/api/unread/{room['id']}/mark-read")
    assert r.status_code == 403


def test_mark_read_empty_room_returns_204_no_op(client: TestClient):
    """mark-read on an empty room is a no-op returning 204."""
    _auth(client, "unr_mk_empty")
    room = _create_room(client, "unr-empty-room")
    r = client.post(f"/api/unread/{room['id']}/mark-read")
    assert r.status_code == 204


def test_mark_read_unauthenticated_returns_401(client: TestClient):
    r = client.post(f"/api/unread/{uuid.uuid4()}/mark-read")
    assert r.status_code == 401


def test_mark_read_is_idempotent(client: TestClient):
    """Calling mark-read twice updates the same receipt without error."""
    _auth(client, "unr_idemp")
    room = _create_room(client, "unr-idemp-room")
    _send(client, room["id"], "x")
    assert client.post(f"/api/unread/{room['id']}/mark-read").status_code == 204
    assert client.post(f"/api/unread/{room['id']}/mark-read").status_code == 204
    r = client.get("/api/unread")
    assert r.json()["counts"][room["id"]] == 0


def test_own_messages_do_not_count_as_unread(client: TestClient):
    """A user's own messages must never appear in their own unread count (spec 08 #45)."""
    _auth(client, "unr_own_owner")
    room = _create_room(client, "unr-own-room", visibility="public")
    # owner sends a baseline message so mark-read has something to anchor on
    _send(client, room["id"], "baseline")

    client.cookies.clear()
    _auth(client, "unr_own_reader")
    client.post(f"/api/rooms/{room['id']}/join")
    # reader marks the room read (anchors receipt at baseline)
    client.post(f"/api/unread/{room['id']}/mark-read")

    # reader sends their own messages after mark-read
    _send(client, room["id"], "my own 1")
    _send(client, room["id"], "my own 2")

    r = client.get("/api/unread")
    # Their own messages must not count
    assert r.json()["counts"][room["id"]] == 0

    # A message from someone else must count
    client.cookies.clear()
    _login(client, "unr_own_owner")
    _send(client, room["id"], "from owner")

    client.cookies.clear()
    _login(client, "unr_own_reader")
    r = client.get("/api/unread")
    assert r.json()["counts"][room["id"]] == 1


def test_deleted_messages_do_not_count_as_unread(client: TestClient):
    _auth(client, "unr_del_owner")
    room = _create_room(client, "unr-del-room", visibility="public")

    client.cookies.clear()
    _auth(client, "unr_del_reader")
    client.post(f"/api/rooms/{room['id']}/join")

    client.cookies.clear()
    _login(client, "unr_del_owner")
    m1 = _send(client, room["id"], "keeper")
    m2 = _send(client, room["id"], "going-away")

    client.cookies.clear()
    _login(client, "unr_del_reader")
    client.post(f"/api/unread/{room['id']}/mark-read")

    client.cookies.clear()
    _login(client, "unr_del_owner")
    _send(client, room["id"], "new1")
    _send(client, room["id"], "new2")
    client.delete(f"/api/rooms/{room['id']}/messages/{m2['id']}")

    client.cookies.clear()
    _login(client, "unr_del_reader")
    r = client.get("/api/unread")
    # Only the 2 new live messages count
    assert r.json()["counts"][room["id"]] == 2
