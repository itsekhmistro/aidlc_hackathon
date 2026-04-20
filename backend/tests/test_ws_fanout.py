"""TASK-16: behavioral tests for the room-member cache and concurrent fanout.

The cache lives on ``PresenceManager`` and is used by every broadcast path
in ``rooms.py`` / ``messages.py``. These tests prove:

* a cache miss queries ``room_member`` once and populates the set
* a second call is served from memory (no DB hit)
* join / leave / ban invalidate the cache so the next read sees reality
* cached entries are per-room (no bleed-over)
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.presence import PresenceManager, presence_manager
from app.models.room import MemberRole, Room, RoomMember, RoomVisibility
from app.models.user import User
from tests.conftest import register_and_login


@pytest.fixture(autouse=True)
def _reset_presence_cache():
    """Every test in this module starts with a clean cache."""
    presence_manager._room_members.clear()
    yield
    presence_manager._room_members.clear()


# ── low-level: PresenceManager directly ──────────────────────────────────────


def _make_user(session: Session, username: str) -> User:
    u = User(
        username=username,
        email=f"{username}@cache.test",
        hashed_password="x",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _make_room(session: Session, name: str, owner: User) -> Room:
    r = Room(
        name=name,
        visibility=RoomVisibility.public.value,
        owner_id=owner.id,
        is_personal=False,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    session.add(RoomMember(room_id=r.id, user_id=owner.id, role=MemberRole.owner.value))
    session.commit()
    return r


def test_cache_miss_populates_and_hit_does_not_query(session: Session):
    pm = PresenceManager()
    owner = _make_user(session, "cacheowner")
    room = _make_room(session, "cache-room-1", owner)

    # First call: miss → queries DB → populates cache.
    members = pm.get_room_members(session, room.id)
    assert members == {owner.id}
    assert room.id in pm._room_members

    # Second call: hit → must not invoke session.exec. Patch it to a
    # detonator and confirm we never call through.
    with patch.object(session, "exec", side_effect=AssertionError("cache miss leaked to DB")):
        cached = pm.get_room_members(session, room.id)
    assert cached == {owner.id}


def test_invalidate_room_forces_reread(session: Session):
    pm = PresenceManager()
    owner = _make_user(session, "cacheowner2")
    room = _make_room(session, "cache-room-2", owner)

    pm.get_room_members(session, room.id)  # populate
    pm.invalidate_room(room.id)
    assert room.id not in pm._room_members

    # Add a second member directly to the DB.
    second = _make_user(session, "cachesecond")
    session.add(RoomMember(room_id=room.id, user_id=second.id, role=MemberRole.member.value))
    session.commit()

    members = pm.get_room_members(session, room.id)
    assert members == {owner.id, second.id}


def test_cache_is_per_room(session: Session):
    pm = PresenceManager()
    owner = _make_user(session, "cacheowner3")
    room_a = _make_room(session, "cache-room-a", owner)
    room_b = _make_room(session, "cache-room-b", owner)

    a_members = pm.get_room_members(session, room_a.id)
    b_members = pm.get_room_members(session, room_b.id)

    # Both contain the same owner, but the underlying set objects are
    # distinct — mutating one must not affect the other.
    assert a_members == {owner.id}
    assert b_members == {owner.id}
    assert pm._room_members[room_a.id] is not pm._room_members[room_b.id]

    # Invalidating A must leave B's cache intact.
    pm.invalidate_room(room_a.id)
    assert room_a.id not in pm._room_members
    assert room_b.id in pm._room_members


def test_invalidate_room_is_safe_on_missing_entry(session: Session):
    pm = PresenceManager()
    # Should not raise.
    pm.invalidate_room(uuid.uuid4())


# ── HTTP-level: join / leave / ban wire invalidation correctly ──────────────


def _auth(client: TestClient, name: str) -> TestClient:
    return register_and_login(client, name, f"{name}@fanout.test")


def _login(client: TestClient, name: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={"email": f"{name}@fanout.test", "password": "password123", "persistent": False},
    )
    assert r.status_code == 200
    return client


def test_join_invalidates_cache_and_next_read_sees_new_member(client: TestClient, session: Session):
    _auth(client, "fanowner1")
    r = client.post("/api/rooms", json={"name": "fan-join-room", "visibility": "public"})
    assert r.status_code == 201
    room_id = uuid.UUID(r.json()["id"])

    # Warm the cache: lookup current members via the presence manager.
    before = presence_manager.get_room_members(session, room_id)
    assert len(before) == 1  # owner only

    # Second user joins.
    client.cookies.clear()
    _auth(client, "fanjoiner1")
    r_join = client.post(f"/api/rooms/{room_id}/join")
    assert r_join.status_code == 204, r_join.text

    # Cache must have been invalidated — next read picks up the new member.
    after = presence_manager.get_room_members(session, room_id)
    assert len(after) == 2


def test_leave_invalidates_cache(client: TestClient, session: Session):
    _auth(client, "fanowner2")
    r = client.post("/api/rooms", json={"name": "fan-leave-room", "visibility": "public"})
    room_id = uuid.UUID(r.json()["id"])

    client.cookies.clear()
    _auth(client, "fanleaver")
    client.post(f"/api/rooms/{room_id}/join")

    # Warm cache with 2 members.
    assert len(presence_manager.get_room_members(session, room_id)) == 2

    # Leaver leaves.
    r_leave = client.post(f"/api/rooms/{room_id}/leave")
    assert r_leave.status_code == 204

    # Cache should reflect the departure.
    assert len(presence_manager.get_room_members(session, room_id)) == 1


def test_ban_invalidates_cache(client: TestClient, session: Session):
    _auth(client, "fanowner3")
    r = client.post("/api/rooms", json={"name": "fan-ban-room", "visibility": "public"})
    room_id = uuid.UUID(r.json()["id"])

    # Second user joins, gets banned.
    client.cookies.clear()
    _auth(client, "fantarget")
    target_id = client.get("/api/auth/me").json()["id"]
    client.post(f"/api/rooms/{room_id}/join")

    assert len(presence_manager.get_room_members(session, room_id)) == 2

    client.cookies.clear()
    _login(client, "fanowner3")
    r_ban = client.delete(f"/api/rooms/{room_id}/members/{target_id}")
    assert r_ban.status_code == 204, r_ban.text

    # Cache must drop the banned user.
    remaining = presence_manager.get_room_members(session, room_id)
    assert len(remaining) == 1
    assert uuid.UUID(target_id) not in remaining


def test_delete_room_invalidates_cache(client: TestClient, session: Session):
    _auth(client, "fanowner4")
    r = client.post("/api/rooms", json={"name": "fan-delete-room", "visibility": "public"})
    room_id = uuid.UUID(r.json()["id"])
    presence_manager.get_room_members(session, room_id)  # populate

    r_del = client.delete(f"/api/rooms/{room_id}")
    assert r_del.status_code == 204

    # The room is gone; the cache entry must be gone too.
    assert room_id not in presence_manager._room_members
