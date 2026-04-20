"""Unit tests for /api/rooms — TASK-04."""
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_login


# ─── helpers ─────────────────────────────────────────────────────────────────


def _auth(client: TestClient, name: str = "alice") -> TestClient:
    """Register user name/name@test.com and return authenticated client."""
    return register_and_login(client, name, f"{name}@test.com")


def _login(client: TestClient, name: str) -> TestClient:
    """Login an already-registered user and return the authenticated client."""
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


def _member_id(client: TestClient, room_id: str, username: str) -> str:
    members = client.get(f"/api/rooms/{room_id}/members").json()
    return next(m["user_id"] for m in members if m["username"] == username)


# ─── POST /api/rooms ──────────────────────────────────────────────────────────


def test_create_room_returns_201_with_owner_as_member(client: TestClient):
    _auth(client, "owner")
    r = client.post("/api/rooms", json={"name": "general", "visibility": "public"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "general"
    assert body["visibility"] == "public"
    assert body["is_personal"] is False
    assert body["member_count"] == 1


def test_create_room_unauthenticated_returns_401(client: TestClient):
    r = client.post("/api/rooms", json={"name": "general", "visibility": "public"})
    assert r.status_code == 401


def test_create_room_duplicate_name_returns_422(client: TestClient):
    _auth(client, "owner")
    _create_room(client, "dup-room")
    r = client.post("/api/rooms", json={"name": "dup-room", "visibility": "public"})
    assert r.status_code == 422
    assert "already taken" in r.json()["detail"]


def test_create_private_room(client: TestClient):
    _auth(client, "owner")
    r = client.post("/api/rooms", json={"name": "secret", "visibility": "private"})
    assert r.status_code == 201
    assert r.json()["visibility"] == "private"


# ─── GET /api/rooms ───────────────────────────────────────────────────────────


def test_list_public_rooms_returns_only_public(client: TestClient):
    _auth(client, "owner")
    _create_room(client, "pub-room", "public")
    _create_room(client, "priv-room", "private")
    r = client.get("/api/rooms")
    assert r.status_code == 200
    names = [room["name"] for room in r.json()]
    assert "pub-room" in names
    assert "priv-room" not in names


def test_list_public_rooms_search_filters_by_name(client: TestClient):
    _auth(client, "owner")
    _create_room(client, "alpha-room")
    _create_room(client, "beta-room")
    r = client.get("/api/rooms?search=alpha")
    assert r.status_code == 200
    names = [room["name"] for room in r.json()]
    assert "alpha-room" in names
    assert "beta-room" not in names


def test_list_public_rooms_unauthenticated_returns_401(client: TestClient):
    r = client.get("/api/rooms")
    assert r.status_code == 401


def test_list_public_rooms_cursor_pagination(client: TestClient):
    _auth(client, "owner")
    _create_room(client, "page-aaa")
    room_b = _create_room(client, "page-bbb")
    _create_room(client, "page-ccc")

    r = client.get(f"/api/rooms?search=page-&cursor={room_b['id']}")
    assert r.status_code == 200
    names = [room["name"] for room in r.json()]
    assert "page-aaa" not in names
    assert "page-bbb" not in names
    assert "page-ccc" in names


# ─── GET /api/rooms/{room_id} ─────────────────────────────────────────────────


def test_get_public_room_returns_room(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "visible-room")
    r = client.get(f"/api/rooms/{room['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == room["id"]


def test_get_private_room_as_non_member_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "secret-room", "private")

    client.cookies.clear()
    _auth(client, "outsider")
    r = client.get(f"/api/rooms/{room['id']}")
    assert r.status_code == 403


def test_get_room_not_found_returns_404(client: TestClient):
    _auth(client, "owner")
    r = client.get(f"/api/rooms/{uuid.uuid4()}")
    assert r.status_code == 404


# ─── PATCH /api/rooms/{room_id} ───────────────────────────────────────────────


def test_update_room_name_as_owner(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "old-name")
    r = client.patch(f"/api/rooms/{room['id']}", json={"name": "new-name"})
    assert r.status_code == 200
    assert r.json()["name"] == "new-name"


def test_update_room_as_non_owner_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "owner-room")

    client.cookies.clear()
    _auth(client, "member")
    client.post(f"/api/rooms/{room['id']}/join")

    r = client.patch(f"/api/rooms/{room['id']}", json={"name": "hijacked"})
    assert r.status_code == 403


def test_update_room_duplicate_name_returns_422(client: TestClient):
    _auth(client, "owner")
    _create_room(client, "taken-name")
    room = _create_room(client, "my-room")
    r = client.patch(f"/api/rooms/{room['id']}", json={"name": "taken-name"})
    assert r.status_code == 422


# ─── DELETE /api/rooms/{room_id} ──────────────────────────────────────────────


def test_delete_room_as_owner_returns_204(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "doomed-room")
    r = client.delete(f"/api/rooms/{room['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/rooms/{room['id']}").status_code == 404


def test_delete_room_as_non_owner_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "guarded-room")

    client.cookies.clear()
    _auth(client, "intruder")
    r = client.delete(f"/api/rooms/{room['id']}")
    assert r.status_code == 403


# ─── POST /api/rooms/{room_id}/join ──────────────────────────────────────────


def test_join_public_room_increments_member_count(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "open-room")

    client.cookies.clear()
    _auth(client, "joiner")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 204
    assert client.get(f"/api/rooms/{room['id']}").json()["member_count"] == 2


def test_join_public_room_is_idempotent(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "idempotent-room")
    # Owner is already a member; joining again should be idempotent
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 204


def test_join_private_room_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "invite-only", "private")

    client.cookies.clear()
    _auth(client, "wannabe")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 403


def test_join_room_banned_user_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "strict-room")

    client.cookies.clear()
    _auth(client, "troublemaker")
    client.post(f"/api/rooms/{room['id']}/join")
    trouble_id = _member_id(client, room["id"], "troublemaker")

    client.cookies.clear()
    _login(client, "owner")
    assert client.delete(f"/api/rooms/{room['id']}/members/{trouble_id}").status_code == 204

    client.cookies.clear()
    _login(client, "troublemaker")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 403


# ─── POST /api/rooms/{room_id}/leave ─────────────────────────────────────────


def test_leave_room_as_member_returns_204(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "leaveable-room")

    client.cookies.clear()
    _auth(client, "leaver")
    client.post(f"/api/rooms/{room['id']}/join")
    assert client.post(f"/api/rooms/{room['id']}/leave").status_code == 204
    assert client.get(f"/api/rooms/{room['id']}").json()["member_count"] == 1


def test_leave_room_as_owner_returns_400(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "permanent-room")
    r = client.post(f"/api/rooms/{room['id']}/leave")
    assert r.status_code == 400
    assert "Owner cannot leave" in r.json()["detail"]


def test_leave_room_not_member_is_idempotent(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "empty-room")

    client.cookies.clear()
    _auth(client, "outsider")
    # outsider never joined — leave is idempotent
    assert client.post(f"/api/rooms/{room['id']}/leave").status_code == 204


# ─── GET /api/rooms/{room_id}/members ────────────────────────────────────────


def test_list_members_returns_all_members(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "member-list-room")

    client.cookies.clear()
    _auth(client, "member1")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 204

    client.cookies.clear()
    _login(client, "owner")
    members = client.get(f"/api/rooms/{room['id']}/members").json()
    assert len(members) == 2
    usernames = {m["username"] for m in members}
    assert {"owner", "member1"} == usernames


def test_list_members_non_member_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "private-members")

    client.cookies.clear()
    _auth(client, "outsider")
    assert client.get(f"/api/rooms/{room['id']}/members").status_code == 403


# ─── Admin grant/remove ───────────────────────────────────────────────────────


def test_grant_admin_as_owner_succeeds(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "admin-grant-room")

    client.cookies.clear()
    _auth(client, "futureadmin")
    client.post(f"/api/rooms/{room['id']}/join")
    fa_id = _member_id(client, room["id"], "futureadmin")

    client.cookies.clear()
    _login(client, "owner")
    assert client.post(f"/api/rooms/{room['id']}/members/{fa_id}/admin").status_code == 204

    members = client.get(f"/api/rooms/{room['id']}/members").json()
    assert next(m["role"] for m in members if m["username"] == "futureadmin") == "admin"


def test_grant_admin_as_non_owner_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "owner-only-admin-room")
    owner_id = _member_id(client, room["id"], "owner")

    client.cookies.clear()
    _auth(client, "plainmember")
    client.post(f"/api/rooms/{room['id']}/join")

    assert client.post(f"/api/rooms/{room['id']}/members/{owner_id}/admin").status_code == 403


def test_grant_admin_to_non_member_returns_404(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "missing-member-room")
    assert client.post(f"/api/rooms/{room['id']}/members/{uuid.uuid4()}/admin").status_code == 404


def test_remove_admin_by_owner_succeeds(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "demote-room")

    client.cookies.clear()
    _auth(client, "tmpadmin")
    client.post(f"/api/rooms/{room['id']}/join")
    ta_id = _member_id(client, room["id"], "tmpadmin")

    client.cookies.clear()
    _login(client, "owner")
    client.post(f"/api/rooms/{room['id']}/members/{ta_id}/admin")
    assert client.delete(f"/api/rooms/{room['id']}/members/{ta_id}/admin").status_code == 204

    members = client.get(f"/api/rooms/{room['id']}/members").json()
    assert next(m["role"] for m in members if m["username"] == "tmpadmin") == "member"


def test_remove_admin_cannot_demote_owner(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "protect-owner-room")
    owner_id = _member_id(client, room["id"], "owner")
    assert client.delete(f"/api/rooms/{room['id']}/members/{owner_id}/admin").status_code == 400


# ─── Ban / unban ──────────────────────────────────────────────────────────────


def test_ban_member_removes_membership_and_blocks_rejoin(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "ban-test-room")

    client.cookies.clear()
    _auth(client, "bannable")
    client.post(f"/api/rooms/{room['id']}/join")
    bannable_id = _member_id(client, room["id"], "bannable")

    client.cookies.clear()
    _login(client, "owner")
    assert client.delete(f"/api/rooms/{room['id']}/members/{bannable_id}").status_code == 204

    members = client.get(f"/api/rooms/{room['id']}/members").json()
    assert not any(m["username"] == "bannable" for m in members)

    client.cookies.clear()
    _login(client, "bannable")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 403


def test_ban_owner_returns_400(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "owner-ban-room")
    owner_id = _member_id(client, room["id"], "owner")
    assert client.delete(f"/api/rooms/{room['id']}/members/{owner_id}").status_code == 400


def test_ban_as_non_admin_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "admin-ban-room")

    client.cookies.clear()
    _auth(client, "regular")
    client.post(f"/api/rooms/{room['id']}/join")

    client.cookies.clear()
    _auth(client, "another")
    client.post(f"/api/rooms/{room['id']}/join")
    another_id = _member_id(client, room["id"], "another")

    client.cookies.clear()
    _login(client, "regular")
    assert client.delete(f"/api/rooms/{room['id']}/members/{another_id}").status_code == 403


def test_list_bans_as_admin_returns_banned_users(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "list-bans-room")

    client.cookies.clear()
    _auth(client, "victim")
    client.post(f"/api/rooms/{room['id']}/join")
    victim_id = _member_id(client, room["id"], "victim")

    client.cookies.clear()
    _login(client, "owner")
    client.delete(f"/api/rooms/{room['id']}/members/{victim_id}")

    bans = client.get(f"/api/rooms/{room['id']}/bans").json()
    assert len(bans) == 1
    assert bans[0]["username"] == "victim"


def test_unban_member_allows_rejoin(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "unban-room")

    client.cookies.clear()
    _auth(client, "pardoned")
    client.post(f"/api/rooms/{room['id']}/join")
    pardoned_id = _member_id(client, room["id"], "pardoned")

    client.cookies.clear()
    _login(client, "owner")
    client.delete(f"/api/rooms/{room['id']}/members/{pardoned_id}")
    assert client.delete(f"/api/rooms/{room['id']}/bans/{pardoned_id}").status_code == 204

    client.cookies.clear()
    _login(client, "pardoned")
    assert client.post(f"/api/rooms/{room['id']}/join").status_code == 204


def test_unban_nonexistent_ban_returns_404(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "unban-404-room")
    assert client.delete(f"/api/rooms/{room['id']}/bans/{uuid.uuid4()}").status_code == 404


# ─── Invitations ─────────────────────────────────────────────────────────────


def test_invite_user_to_private_room_creates_invitation(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "invite-room", "private")

    client.cookies.clear()
    _auth(client, "invitee")

    client.cookies.clear()
    _login(client, "owner")
    r = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "invitee"})
    assert r.status_code == 201
    assert r.json()["invited_user_id"] is not None


def test_invite_already_member_returns_400(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "invite-member-room")
    r = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "owner"})
    assert r.status_code == 400
    assert "already a member" in r.json()["detail"]


def test_invite_nonexistent_user_returns_404(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "invite-ghost-room")
    r = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "ghost_user_xyz"})
    assert r.status_code == 404


def test_invite_duplicate_is_idempotent(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "idempotent-invite-room", "private")

    client.cookies.clear()
    _auth(client, "invitee2")

    client.cookies.clear()
    _login(client, "owner")
    r1 = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "invitee2"})
    r2 = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "invitee2"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_my_invitations_returns_pending_only(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "my-invites-room", "private")

    client.cookies.clear()
    _auth(client, "invitedperson")

    client.cookies.clear()
    _login(client, "owner")
    client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "invitedperson"})

    client.cookies.clear()
    _login(client, "invitedperson")
    invites = client.get("/api/rooms/invitations/mine").json()
    assert len(invites) == 1
    assert invites[0]["room_id"] == room["id"]


def test_accept_invitation_adds_to_room(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "accept-invite-room", "private")

    client.cookies.clear()
    _auth(client, "accepteduser")

    client.cookies.clear()
    _login(client, "owner")
    invite = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "accepteduser"}).json()

    client.cookies.clear()
    _login(client, "accepteduser")
    assert client.post(f"/api/rooms/invitations/{invite['id']}/accept").status_code == 204

    r2 = client.get(f"/api/rooms/{room['id']}")
    assert r2.status_code == 200
    assert r2.json()["member_count"] == 2


def test_accept_invitation_wrong_user_returns_404(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "wrong-user-accept-room", "private")

    client.cookies.clear()
    _auth(client, "realinvitee")

    client.cookies.clear()
    _login(client, "owner")
    invite = client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "realinvitee"}).json()

    client.cookies.clear()
    _auth(client, "interloper")
    assert client.post(f"/api/rooms/invitations/{invite['id']}/accept").status_code == 404


def test_list_invitations_as_admin_returns_pending(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "list-invite-room", "private")

    client.cookies.clear()
    _auth(client, "pendinguser")

    client.cookies.clear()
    _login(client, "owner")
    client.post(f"/api/rooms/{room['id']}/invitations", json={"username": "pendinguser"})

    invites = client.get(f"/api/rooms/{room['id']}/invitations").json()
    assert len(invites) == 1


def test_list_invitations_as_non_admin_returns_403(client: TestClient):
    _auth(client, "owner")
    room = _create_room(client, "403-invite-room", "private")

    client.cookies.clear()
    _auth(client, "plainquest")
    assert client.get(f"/api/rooms/{room['id']}/invitations").status_code == 403


# ─── GET /api/rooms/mine ──────────────────────────────────────────────────────


def test_list_mine_returns_only_member_rooms(client: TestClient):
    """GET /api/rooms/mine returns only rooms the authenticated user is a member of."""
    _auth(client, "mineowner")
    room_mine = _create_room(client, "my-private-room", "private")

    client.cookies.clear()
    _auth(client, "mineother")
    _create_room(client, "other-room", "public")

    client.cookies.clear()
    _login(client, "mineowner")
    rooms = client.get("/api/rooms/mine").json()
    room_ids = [r["id"] for r in rooms]
    assert room_mine["id"] in room_ids
    # other-room should NOT be in mineowner's rooms (not a member)
    other_names = [r["name"] for r in rooms]
    assert "other-room" not in other_names


def test_list_mine_unauthenticated_returns_401(client: TestClient):
    r = client.get("/api/rooms/mine")
    assert r.status_code == 401


def test_list_mine_includes_joined_public_rooms(client: TestClient):
    """Rooms the user joined (not just created) also appear in /mine."""
    _auth(client, "pubowner")
    pub_room = _create_room(client, "joinable-mine-room", "public")

    client.cookies.clear()
    _auth(client, "joiner_mine")
    client.post(f"/api/rooms/{pub_room['id']}/join")

    rooms = client.get("/api/rooms/mine").json()
    ids = [r["id"] for r in rooms]
    assert pub_room["id"] in ids
