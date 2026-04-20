"""Unit tests for /api/rooms/{room_id}/messages — TASK-06."""
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_login


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


def _create_room(client: TestClient, name: str, visibility: str = "public") -> dict:
    r = client.post("/api/rooms", json={"name": name, "visibility": visibility})
    assert r.status_code == 201, r.text
    return r.json()


def _send_message(client: TestClient, room_id: str, content: str) -> dict:
    r = client.post(f"/api/rooms/{room_id}/messages", json={"content": content})
    assert r.status_code == 201, r.text
    return r.json()


# ─── GET /api/rooms/{room_id}/messages ───────────────────────────────────────


def test_list_messages_returns_message_page(client: TestClient):
    _auth(client, "msgowner1")
    room = _create_room(client, "msg-list-room")
    _send_message(client, room["id"], "Hello World")
    r = client.get(f"/api/rooms/{room['id']}/messages")
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    assert "has_more" in data
    assert "next_cursor" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello World"
    assert data["has_more"] is False


def test_list_messages_non_member_returns_403(client: TestClient):
    _auth(client, "msgowner2")
    room = _create_room(client, "msg-403-room")
    client.cookies.clear()
    _auth(client, "outsider_msg")
    r = client.get(f"/api/rooms/{room['id']}/messages")
    assert r.status_code == 403


def test_list_messages_empty_room(client: TestClient):
    _auth(client, "msgowner3")
    room = _create_room(client, "empty-msg-room")
    r = client.get(f"/api/rooms/{room['id']}/messages")
    assert r.status_code == 200
    data = r.json()
    assert data["messages"] == []
    assert data["has_more"] is False
    assert data["next_cursor"] is None


def test_list_messages_unauthenticated_returns_401(client: TestClient):
    r = client.get(f"/api/rooms/{uuid.uuid4()}/messages")
    assert r.status_code == 401


# ─── POST /api/rooms/{room_id}/messages ──────────────────────────────────────


def test_send_message_happy_path_returns_201(client: TestClient):
    _auth(client, "msgowner4")
    room = _create_room(client, "send-msg-room")
    r = client.post(f"/api/rooms/{room['id']}/messages", json={"content": "Hey there"})
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "Hey there"
    assert data["room_id"] == room["id"]
    assert data["author_username"] == "msgowner4"
    assert data["deleted"] is False
    assert data["edited_at"] is None


def test_send_message_non_member_returns_403(client: TestClient):
    _auth(client, "msgowner5")
    room = _create_room(client, "send-msg-403-room")
    client.cookies.clear()
    _auth(client, "outsider_send")
    r = client.post(f"/api/rooms/{room['id']}/messages", json={"content": "Hacked"})
    assert r.status_code == 403


def test_send_message_unauthenticated_returns_401(client: TestClient):
    r = client.post(f"/api/rooms/{uuid.uuid4()}/messages", json={"content": "Anon"})
    assert r.status_code == 401


# ─── PATCH /api/rooms/{room_id}/messages/{id} ────────────────────────────────


def test_edit_message_by_author_updates_content(client: TestClient):
    _auth(client, "msgowner6")
    room = _create_room(client, "edit-msg-room")
    msg = _send_message(client, room["id"], "Original content")
    r = client.patch(
        f"/api/rooms/{room['id']}/messages/{msg['id']}",
        json={"content": "Edited content"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "Edited content"
    assert data["edited_at"] is not None


def test_edit_message_by_non_author_returns_403(client: TestClient):
    _auth(client, "msgowner7")
    room = _create_room(client, "edit-msg-403-room")
    msg = _send_message(client, room["id"], "Author message")

    client.cookies.clear()
    _auth(client, "member_edit")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.patch(
        f"/api/rooms/{room['id']}/messages/{msg['id']}",
        json={"content": "Hijacked"},
    )
    assert r.status_code == 403


def test_edit_message_not_found_returns_404(client: TestClient):
    _auth(client, "msgowner8")
    room = _create_room(client, "edit-msg-404-room")
    r = client.patch(
        f"/api/rooms/{room['id']}/messages/{uuid.uuid4()}",
        json={"content": "Ghost edit"},
    )
    assert r.status_code == 404


def test_edit_message_unauthenticated_returns_401(client: TestClient):
    r = client.patch(
        f"/api/rooms/{uuid.uuid4()}/messages/{uuid.uuid4()}",
        json={"content": "Anon edit"},
    )
    assert r.status_code == 401


# ─── DELETE /api/rooms/{room_id}/messages/{id} ───────────────────────────────


def test_delete_message_by_author_returns_204(client: TestClient):
    _auth(client, "msgowner9")
    room = _create_room(client, "del-msg-room")
    msg = _send_message(client, room["id"], "To be deleted")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")
    assert r.status_code == 204


def test_delete_message_clears_content(client: TestClient):
    """After soft-delete, content is cleared and deleted flag is True."""
    _auth(client, "msgowner10")
    room = _create_room(client, "del-msg-clear-room")
    msg = _send_message(client, room["id"], "Secret content")
    client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")

    # Re-fetch messages to verify
    r = client.get(f"/api/rooms/{room['id']}/messages")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["content"] == ""
    assert msgs[0]["deleted"] is True


def test_delete_message_by_non_author_returns_403(client: TestClient):
    _auth(client, "msgowner11")
    room = _create_room(client, "del-msg-403-room")
    msg = _send_message(client, room["id"], "Protected message")

    client.cookies.clear()
    _auth(client, "member_del")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")
    assert r.status_code == 403


def test_delete_message_not_found_returns_404(client: TestClient):
    _auth(client, "msgowner12")
    room = _create_room(client, "del-msg-404-room")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_message_unauthenticated_returns_401(client: TestClient):
    r = client.delete(f"/api/rooms/{uuid.uuid4()}/messages/{uuid.uuid4()}")
    assert r.status_code == 401
