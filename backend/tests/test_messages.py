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
    # TASK-16: client_msg_id is always present in the response schema; when
    # the caller didn't supply one it echoes back None.
    assert data["client_msg_id"] is None


def test_send_message_echoes_client_msg_id_in_response_and_ws(client: TestClient):
    """TASK-16: harness-supplied client_msg_id must appear in (a) the HTTP
    201 body and (b) the `message.new` event delivered to a second member
    of the room. Load test harness uses this to compute e2e latency."""
    from app.core.presence import presence_manager

    # Reset any leftover cache state between tests.
    presence_manager._room_members.clear()
    presence_manager.connections.clear()
    presence_manager.tab_status.clear()

    _auth(client, "cmidowner")
    room = _create_room(client, "cmid-room")

    client.cookies.clear()
    _auth(client, "cmidreceiver")
    r_join = client.post(f"/api/rooms/{room['id']}/join")
    assert r_join.status_code in (200, 204), r_join.text

    with client.websocket_connect("/ws?tab_id=cmid-tab") as ws:
        # Drain the initial presence.bulk.
        first = ws.receive_json()
        assert first["type"] == "presence.bulk"

        # Author posts with a correlation id. (Switch auth cookie.)
        client.cookies.clear()
        r_login = client.post(
            "/api/auth/login",
            json={
                "email": "cmidowner@test.com",
                "password": "password123",
                "persistent": False,
            },
        )
        assert r_login.status_code == 200, r_login.text

        r_post = client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"content": "hello", "client_msg_id": "abc123"},
        )
        assert r_post.status_code == 201, r_post.text
        assert r_post.json()["client_msg_id"] == "abc123"

        # Receiver's WS gets message.new with the id echoed through.
        # Drain until we see message.new (we may get unread.increment first).
        seen = None
        for _ in range(5):
            ev = ws.receive_json()
            if ev.get("type") == "message.new":
                seen = ev
                break
        assert seen is not None, "never received message.new"
        assert seen["message"]["client_msg_id"] == "abc123"


def test_history_read_does_not_echo_client_msg_id(client: TestClient):
    """`client_msg_id` is per-request only — never persisted, always None on
    history reads."""
    _auth(client, "cmidhistory")
    room = _create_room(client, "cmid-history-room")
    client.post(
        f"/api/rooms/{room['id']}/messages",
        json={"content": "with correlation", "client_msg_id": "xyz789"},
    )
    r = client.get(f"/api/rooms/{room['id']}/messages")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["client_msg_id"] is None


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


def test_delete_message_by_room_owner_returns_204(client: TestClient):
    """Room owner can delete another user's message (spec 06.4)."""
    _auth(client, "ownerdel1")
    room = _create_room(client, "owner-del-room")

    # Another user joins and posts a message.
    client.cookies.clear()
    _auth(client, "memberdel1")
    r_join = client.post(f"/api/rooms/{room['id']}/join")
    assert r_join.status_code in (200, 204), r_join.text
    msg = _send_message(client, room["id"], "member's message")

    # Owner deletes the member's message.
    client.cookies.clear()
    _login(client, "ownerdel1")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")
    assert r.status_code == 204, r.text

    # Verify message is soft-deleted.
    r_list = client.get(f"/api/rooms/{room['id']}/messages")
    msgs = r_list.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["deleted"] is True
    assert msgs[0]["content"] == ""


def test_delete_message_by_room_admin_returns_204(client: TestClient):
    """Room admin can delete another user's message (spec 06.4)."""
    _auth(client, "ownerdel2")
    room = _create_room(client, "admin-del-room")

    # Promote a second user to admin.
    client.cookies.clear()
    _auth(client, "admindel2")
    admin_id = client.get("/api/auth/me").json()["id"]
    r_join = client.post(f"/api/rooms/{room['id']}/join")
    assert r_join.status_code in (200, 204), r_join.text

    client.cookies.clear()
    _login(client, "ownerdel2")
    r_grant = client.post(f"/api/rooms/{room['id']}/members/{admin_id}/admin")
    assert r_grant.status_code == 204, r_grant.text

    # A regular member joins and posts a message.
    client.cookies.clear()
    _auth(client, "memberdel2")
    client.post(f"/api/rooms/{room['id']}/join")
    msg = _send_message(client, room["id"], "message from member")

    # Admin deletes the regular member's message.
    client.cookies.clear()
    _login(client, "admindel2")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")
    assert r.status_code == 204, r.text


def test_delete_message_by_regular_member_returns_403(client: TestClient):
    """Regular member cannot delete another user's message (spec 06.4)."""
    _auth(client, "ownerdel3")
    room = _create_room(client, "member-del-403-room")
    msg = _send_message(client, room["id"], "owner's message")

    client.cookies.clear()
    _auth(client, "memberdel3")
    client.post(f"/api/rooms/{room['id']}/join")

    r = client.delete(f"/api/rooms/{room['id']}/messages/{msg['id']}")
    assert r.status_code == 403, r.text
    assert "admin" in r.json()["detail"].lower()


def test_delete_message_not_found_returns_404(client: TestClient):
    _auth(client, "msgowner12")
    room = _create_room(client, "del-msg-404-room")
    r = client.delete(f"/api/rooms/{room['id']}/messages/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_message_unauthenticated_returns_401(client: TestClient):
    r = client.delete(f"/api/rooms/{uuid.uuid4()}/messages/{uuid.uuid4()}")
    assert r.status_code == 401


# ─── scope guards for TASK-04/06 gap fixes ───────────────────────────────────


def test_post_in_public_room_not_blocked_by_user_ban(client: TestClient):
    """User-ban enforcement is scoped to personal rooms; a public room
    containing both banner and banned must still accept messages from both
    sides. Guards against the ban check being accidentally widened."""
    # Owner creates a public room.
    _auth(client, "pubowner")
    room = _create_room(client, "pub-ban-scope-room")
    room_id = room["id"]

    # Second user joins.
    client.cookies.clear()
    _auth(client, "pubmember")
    pubmember_id = client.get("/api/auth/me").json()["id"]
    r_join = client.post(f"/api/rooms/{room_id}/join")
    assert r_join.status_code in (200, 204), r_join.text

    # pubmember bans pubowner.
    owner_id = None
    client.cookies.clear()
    _login(client, "pubowner")
    owner_id = client.get("/api/auth/me").json()["id"]

    client.cookies.clear()
    _login(client, "pubmember")
    r_ban = client.post("/api/bans", json={"banned_id": owner_id})
    assert r_ban.status_code == 201, r_ban.text

    # Despite the ban, pubmember can still post in the PUBLIC room.
    r_post = client.post(f"/api/rooms/{room_id}/messages", json={"content": "hello public"})
    assert r_post.status_code == 201, r_post.text

    # And pubowner can still post there too.
    client.cookies.clear()
    _login(client, "pubowner")
    r_post_owner = client.post(f"/api/rooms/{room_id}/messages", json={"content": "hi back"})
    assert r_post_owner.status_code == 201, r_post_owner.text
    _ = pubmember_id  # silence unused


def test_admin_role_is_per_room_cannot_delete_in_other_room(client: TestClient):
    """Admin role is granted per-room. A user who is admin in room X must
    NOT be able to delete messages in room Y where they are a regular
    member. Guards against the delete authorization check looking up the
    role globally instead of scoping it to the target room."""
    # User 1 owns room X and promotes user 2 to admin there.
    _auth(client, "ownerX")
    room_x = _create_room(client, "scope-room-x")

    client.cookies.clear()
    _auth(client, "adminInX")
    admin_in_x_id = client.get("/api/auth/me").json()["id"]
    client.post(f"/api/rooms/{room_x['id']}/join")

    client.cookies.clear()
    _login(client, "ownerX")
    r_grant = client.post(f"/api/rooms/{room_x['id']}/members/{admin_in_x_id}/admin")
    assert r_grant.status_code == 204, r_grant.text

    # Separate owner creates room Y; adminInX joins as a plain member.
    client.cookies.clear()
    _auth(client, "ownerY")
    room_y = _create_room(client, "scope-room-y")
    msg_y = _send_message(client, room_y["id"], "ownerY's message in Y")

    client.cookies.clear()
    _login(client, "adminInX")
    r_join_y = client.post(f"/api/rooms/{room_y['id']}/join")
    assert r_join_y.status_code in (200, 204), r_join_y.text

    # adminInX (regular member in room Y) cannot delete ownerY's message.
    r_del = client.delete(f"/api/rooms/{room_y['id']}/messages/{msg_y['id']}")
    assert r_del.status_code == 403, r_del.text
    assert "admin" in r_del.json()["detail"].lower()
