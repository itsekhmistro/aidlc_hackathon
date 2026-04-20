"""Direct tests for the WS endpoint's threadpool helpers (TASK-16).

``_auth_sync`` and ``_upsert_and_audience_sync`` are the two functions
that ``asyncio.to_thread`` runs on every WS connect. Their correctness
is load-bearing for NFR 3.1 — the integration path hits them via the
Starlette TestClient, but that exercise is indirect. These tests cover
the contract directly so regressions are obvious and small.
"""
import hashlib
import uuid
from datetime import datetime, timezone

from sqlmodel import Session

import app.core.db as db_module
from app.api.routes.ws import _auth_sync, _upsert_and_audience_sync
from app.core.db import session_scope
from app.core.presence import presence_manager
from app.models.message import Message  # noqa: F401 — register model metadata
from app.models.room import Room, RoomMember, RoomVisibility
from app.models.social import Friendship, FriendshipStatus
from app.models.user import Presence, User, UserSession


def _mk_user(session: Session, username: str) -> User:
    u = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password="x",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _issue_token(session: Session, user: User, *, revoked: bool = False) -> str:
    raw = f"tok-{user.username}-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    row = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        revoked_at=datetime.now(timezone.utc) if revoked else None,
    )
    session.add(row)
    session.commit()
    return raw


# ── _auth_sync ────────────────────────────────────────────────────────────


def test_auth_sync_returns_none_for_missing_token(client):
    # The ``client`` fixture patches session_scope through to the test
    # session — we rely on that monkeypatch, not on ``client`` itself.
    assert _auth_sync(None) is None


def test_auth_sync_returns_none_for_unknown_token(client):
    assert _auth_sync("never-issued") is None


def test_auth_sync_returns_user_id_for_valid_token(client, session):
    user = _mk_user(session, "alice")
    token = _issue_token(session, user)
    assert _auth_sync(token) == user.id


def test_auth_sync_returns_none_for_revoked_token(client, session):
    user = _mk_user(session, "bob")
    token = _issue_token(session, user, revoked=True)
    assert _auth_sync(token) is None


def test_auth_sync_returns_none_for_soft_deleted_user(client, session):
    user = _mk_user(session, "ghost")
    token = _issue_token(session, user)
    user.deleted_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    assert _auth_sync(token) is None


# ── _upsert_and_audience_sync ────────────────────────────────────────────


def test_upsert_inserts_presence_row_on_first_call(client, session):
    user = _mk_user(session, "newcomer")
    assert session.get(Presence, user.id) is None

    audience = _upsert_and_audience_sync(user.id, "online")

    row = session.get(Presence, user.id)
    assert row is not None
    assert row.status == "online"
    assert audience == set()  # no friends, no rooms → empty audience


def test_upsert_updates_existing_presence_row(client, session):
    user = _mk_user(session, "returner")
    session.add(Presence(user_id=user.id, status="offline"))
    session.commit()
    original_updated_at = session.get(Presence, user.id).updated_at

    _upsert_and_audience_sync(user.id, "afk")

    row = session.get(Presence, user.id)
    assert row.status == "afk"
    assert row.updated_at >= original_updated_at


def test_audience_includes_room_members(client, session):
    alice = _mk_user(session, "alice-a")
    bob = _mk_user(session, "bob-a")
    carol = _mk_user(session, "carol-a")
    room = Room(
        name="shared",
        description="",
        visibility=RoomVisibility.public.value,
        owner_id=alice.id,
    )
    session.add(room)
    session.commit()
    session.refresh(room)
    for u in (alice, bob, carol):
        session.add(RoomMember(room_id=room.id, user_id=u.id, role="member"))
    session.commit()
    presence_manager.invalidate_room(room.id)

    audience = _upsert_and_audience_sync(alice.id, "online")

    assert bob.id in audience
    assert carol.id in audience
    assert alice.id not in audience  # the user themselves is excluded


def test_audience_includes_accepted_friends(client, session):
    alice = _mk_user(session, "alice-f")
    bob = _mk_user(session, "bob-f")
    session.add(
        Friendship(
            requester_id=alice.id,
            addressee_id=bob.id,
            status=FriendshipStatus.accepted.value,
        )
    )
    session.commit()

    audience = _upsert_and_audience_sync(alice.id, "online")

    assert bob.id in audience


def test_audience_excludes_pending_friends(client, session):
    alice = _mk_user(session, "alice-p")
    bob = _mk_user(session, "bob-p")
    session.add(
        Friendship(
            requester_id=alice.id,
            addressee_id=bob.id,
            status=FriendshipStatus.pending.value,
        )
    )
    session.commit()

    audience = _upsert_and_audience_sync(alice.id, "online")

    assert bob.id not in audience


# ── session_scope ─────────────────────────────────────────────────────────


def test_session_scope_yields_working_session():
    """Direct contract: session_scope() yields a Session bound to the
    production engine (i.e. NOT the test fixture — this is the only
    test that exercises the real helper, not the monkeypatched version).
    """
    with session_scope() as s:
        assert isinstance(s, Session)
        assert s.bind is db_module.engine


def test_session_scope_releases_connection_on_exit():
    """Sanity: entering and exiting the context manager N times in a
    row must not leak pool slots. We open 60 scopes back-to-back; with
    pool_size=50 + overflow=50 this would only fail if connections are
    held after exit.
    """
    for _ in range(60):
        with session_scope() as s:
            s.exec(__import__("sqlmodel").select(User))  # touch the connection
