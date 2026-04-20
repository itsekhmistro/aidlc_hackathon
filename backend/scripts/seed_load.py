"""TASK-16 load-test seeder.

Populates the database with synthetic users, rooms, memberships, and
messages for the Locust harness. All rows are tagged with a ``loadtest_``
prefix (usernames, emails, room names) so they are separable from real
hackathon data and removable via ``--reset``.

Usage::

    uv run python -m scripts.seed_load --help

Design choices:

* One bcrypt hash, reused across every user. Bcrypt cost 12 × 300 users
  serial would burn ~90 s; this keeps the whole seed under a second.
* Users, memberships and messages are bulk-inserted via
  ``session.execute(insert(Model), [...])`` to avoid per-row overhead.
* Session rows use the real ``app.core.security.create_session_token``
  helper so the harness can authenticate through the normal cookie path
  (no test-only endpoint is introduced).
* Messages are seeded with ``created_at = now - i*seconds`` so keyset
  pagination returns realistic monotonic ordering.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import delete, insert
from sqlmodel import Session, select

from app.core.db import engine
from app.core.security import create_session_token, get_password_hash
from app.models.message import Message
from app.models.room import MemberRole, Room, RoomMember, RoomVisibility
from app.models.user import User, UserSession

log = logging.getLogger("seed_load")

LOADTEST_PREFIX = "loadtest_"
DEFAULT_PASSWORD = "loadtest-password"
MESSAGE_BATCH = 1000


@dataclass
class SeedArgs:
    users: int
    rooms: int
    members_per_room: int
    messages: int
    big_room_size: int
    big_room_history: int
    history_room_size: int
    history_room_messages: int
    reset: bool
    token_out: Path | None


def parse_args(argv: list[str] | None = None) -> SeedArgs:
    parser = argparse.ArgumentParser(
        prog="seed_load",
        description="Seed a database with load-test data (TASK-16).",
    )
    parser.add_argument("--users", type=int, default=300)
    parser.add_argument("--rooms", type=int, default=30)
    parser.add_argument("--members-per-room", type=int, default=10)
    parser.add_argument("--messages", type=int, default=0,
                        help="Plain per-room message count (each of --rooms).")
    parser.add_argument("--big-room-size", type=int, default=1000,
                        help="Members in the dedicated fanout room.")
    parser.add_argument("--big-room-history", type=int, default=0,
                        help="Messages seeded into the big fanout room.")
    parser.add_argument("--history-room-size", type=int, default=0,
                        help="Members in the dedicated history-test room.")
    parser.add_argument("--history-room-messages", type=int, default=10_000)
    parser.add_argument("--reset", action="store_true",
                        help="Delete load-test rows (by loadtest_ prefix) before seeding.")
    parser.add_argument("--token-out", type=Path, default=None,
                        help="Write [{user_id, username, session_token}] JSON for the harness.")
    ns = parser.parse_args(argv)
    return SeedArgs(
        users=ns.users,
        rooms=ns.rooms,
        members_per_room=ns.members_per_room,
        messages=ns.messages,
        big_room_size=ns.big_room_size,
        big_room_history=ns.big_room_history,
        history_room_size=ns.history_room_size,
        history_room_messages=ns.history_room_messages,
        reset=ns.reset,
        token_out=ns.token_out,
    )


# ── reset ────────────────────────────────────────────────────────────────────


def reset_loadtest(session: Session) -> None:
    """Drop every row whose user/room was seeded by this script.

    Order matters (FKs): messages → members → bans → invitations → rooms
    → sessions → users. We find all targeted users/rooms by prefix once,
    then delete everything referencing those IDs.
    """
    loadtest_user_ids = [
        row for row in session.exec(
            select(User.id).where(User.username.like(f"{LOADTEST_PREFIX}%"))  # type: ignore[attr-defined]
        ).all()
    ]
    loadtest_room_ids = [
        row for row in session.exec(
            select(Room.id).where(Room.name.like(f"{LOADTEST_PREFIX}%"))  # type: ignore[attr-defined]
        ).all()
    ]

    if not loadtest_user_ids and not loadtest_room_ids:
        log.info("reset: nothing to delete")
        return

    from app.models.message import Attachment, ReadReceipt
    from app.models.room import RoomBan, RoomInvitation
    from app.models.social import Friendship, UserBan

    if loadtest_room_ids:
        session.execute(delete(Message).where(Message.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(Attachment).where(Attachment.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(ReadReceipt).where(ReadReceipt.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(RoomMember).where(RoomMember.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(RoomBan).where(RoomBan.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(RoomInvitation).where(RoomInvitation.room_id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]
        session.execute(delete(Room).where(Room.id.in_(loadtest_room_ids)))  # type: ignore[attr-defined]

    if loadtest_user_ids:
        # Clean up any remaining cross-references from our test users to
        # non-loadtest rooms (defensive — should be empty in practice).
        session.execute(delete(RoomMember).where(RoomMember.user_id.in_(loadtest_user_ids)))  # type: ignore[attr-defined]
        session.execute(
            delete(Message).where(Message.author_id.in_(loadtest_user_ids))  # type: ignore[attr-defined]
        )
        session.execute(delete(UserSession).where(UserSession.user_id.in_(loadtest_user_ids)))  # type: ignore[attr-defined]
        session.execute(
            delete(Friendship).where(
                Friendship.requester_id.in_(loadtest_user_ids)  # type: ignore[attr-defined]
                | Friendship.addressee_id.in_(loadtest_user_ids)  # type: ignore[attr-defined]
            )
        )
        session.execute(
            delete(UserBan).where(
                UserBan.banner_id.in_(loadtest_user_ids)  # type: ignore[attr-defined]
                | UserBan.banned_id.in_(loadtest_user_ids)  # type: ignore[attr-defined]
            )
        )
        session.execute(delete(User).where(User.id.in_(loadtest_user_ids)))  # type: ignore[attr-defined]

    session.commit()
    log.info(
        "reset: dropped %d users / %d rooms",
        len(loadtest_user_ids), len(loadtest_room_ids),
    )


# ── seed ─────────────────────────────────────────────────────────────────────


def _existing_usernames(session: Session) -> set[str]:
    rows = session.exec(
        select(User.username).where(User.username.like(f"{LOADTEST_PREFIX}%"))  # type: ignore[attr-defined]
    ).all()
    return set(rows)


def seed_users(session: Session, n: int, hashed_pw: str) -> list[uuid.UUID]:
    """Insert ``n`` users named ``loadtest_<i>`` idempotently.

    Returns the full ordered list of user ids for i=0..n-1.
    """
    existing = _existing_usernames(session)
    # Build the full target list (existing + new) keyed by the ordered name
    # so ``big_room_size`` / membership-per-room math stays deterministic.
    new_rows = []
    all_ids: list[uuid.UUID] = []
    existing_map = {
        u.username: u.id
        for u in session.exec(
            select(User).where(User.username.like(f"{LOADTEST_PREFIX}%"))  # type: ignore[attr-defined]
        ).all()
    }
    now = datetime.now(timezone.utc)
    for i in range(n):
        username = f"{LOADTEST_PREFIX}{i}"
        if username in existing:
            all_ids.append(existing_map[username])
            continue
        uid = uuid.uuid4()
        all_ids.append(uid)
        new_rows.append({
            "id": uid,
            "username": username,
            "email": f"{LOADTEST_PREFIX}{i}@example.com",
            "hashed_password": hashed_pw,
            "created_at": now,
            "deleted_at": None,
        })
    if new_rows:
        session.execute(insert(User), new_rows)
        session.commit()
    log.info("users: %d total (%d new)", len(all_ids), len(new_rows))
    return all_ids


def _existing_room_names(session: Session) -> dict[str, uuid.UUID]:
    return {
        r.name: r.id
        for r in session.exec(
            select(Room).where(Room.name.like(f"{LOADTEST_PREFIX}%"))  # type: ignore[attr-defined]
        ).all()
    }


def seed_rooms(
    session: Session,
    *,
    plain_rooms: int,
    big_room_size: int,
    history_room_size: int,
    owner_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """Create plain rooms + optionally a big fanout room and a history room."""
    existing = _existing_room_names(session)
    names: list[str] = [f"{LOADTEST_PREFIX}room_{i}" for i in range(plain_rooms)]
    if big_room_size > 0:
        names.append(f"{LOADTEST_PREFIX}bigroom")
    if history_room_size > 0:
        names.append(f"{LOADTEST_PREFIX}history")

    new_rows = []
    result: dict[str, uuid.UUID] = {}
    now = datetime.now(timezone.utc)
    for name in names:
        if name in existing:
            result[name] = existing[name]
            continue
        rid = uuid.uuid4()
        result[name] = rid
        new_rows.append({
            "id": rid,
            "name": name,
            "description": None,
            "visibility": RoomVisibility.public.value,
            "owner_id": owner_id,
            "is_personal": False,
            "created_at": now,
        })
    if new_rows:
        session.execute(insert(Room), new_rows)
        session.commit()
    log.info("rooms: %d total (%d new)", len(result), len(new_rows))
    return result


def _existing_memberships(session: Session, room_ids: Iterable[uuid.UUID]) -> set[tuple[uuid.UUID, uuid.UUID]]:
    rows = session.exec(
        select(RoomMember.room_id, RoomMember.user_id).where(
            RoomMember.room_id.in_(list(room_ids))  # type: ignore[attr-defined]
        )
    ).all()
    return {(rid, uid) for rid, uid in rows}


def seed_memberships(
    session: Session,
    *,
    plain_room_ids: list[uuid.UUID],
    members_per_room: int,
    big_room_id: uuid.UUID | None,
    big_room_size: int,
    history_room_id: uuid.UUID | None,
    history_room_size: int,
    user_ids: list[uuid.UUID],
    owner_id: uuid.UUID,
) -> int:
    """Insert ``RoomMember`` rows idempotently.

    Plain rooms: each gets ``members_per_room`` users picked round-robin
    from the user pool. Big room: first ``big_room_size`` users join.
    History room: first ``history_room_size`` users join.
    """
    all_room_ids = list(plain_room_ids)
    if big_room_id is not None:
        all_room_ids.append(big_room_id)
    if history_room_id is not None:
        all_room_ids.append(history_room_id)
    existing = _existing_memberships(session, all_room_ids)

    rows: list[dict] = []
    now = datetime.now(timezone.utc)

    def _add(room_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        if (room_id, user_id) in existing:
            return
        rows.append({
            "room_id": room_id,
            "user_id": user_id,
            "role": role,
            "joined_at": now,
        })
        existing.add((room_id, user_id))

    # Owner is always the first loadtest user; mark them owner everywhere.
    for rid in all_room_ids:
        _add(rid, owner_id, MemberRole.owner.value)

    for idx, rid in enumerate(plain_room_ids):
        # rotate through the user list so rooms don't all contain the same set
        for k in range(members_per_room):
            uid = user_ids[(idx + k) % len(user_ids)]
            _add(rid, uid, MemberRole.member.value)

    if big_room_id is not None and big_room_size > 0:
        for uid in user_ids[:big_room_size]:
            _add(big_room_id, uid, MemberRole.member.value)

    if history_room_id is not None and history_room_size > 0:
        for uid in user_ids[:history_room_size]:
            _add(history_room_id, uid, MemberRole.member.value)

    if rows:
        session.execute(insert(RoomMember), rows)
        session.commit()
    log.info("memberships: %d new rows", len(rows))
    return len(rows)


def seed_messages(
    session: Session,
    *,
    room_id: uuid.UUID,
    author_ids: list[uuid.UUID],
    count: int,
) -> int:
    """Seed ``count`` messages into ``room_id``, batched in 1000-row chunks.

    ``created_at`` decreases by 1 s per message so the highest index is the
    oldest. This lets keyset pagination walk realistic history.
    """
    if count <= 0 or not author_ids:
        return 0
    base = datetime.now(timezone.utc)
    inserted = 0
    batch: list[dict] = []
    for i in range(count):
        batch.append({
            "id": uuid.uuid4(),
            "room_id": room_id,
            "author_id": author_ids[i % len(author_ids)],
            "content": f"loadtest message {i}",
            "reply_to_id": None,
            "created_at": base - timedelta(seconds=i),
            "edited_at": None,
            "deleted_at": None,
        })
        if len(batch) >= MESSAGE_BATCH:
            session.execute(insert(Message), batch)
            session.commit()
            inserted += len(batch)
            batch.clear()
    if batch:
        session.execute(insert(Message), batch)
        session.commit()
        inserted += len(batch)
    return inserted


# ── session tokens ───────────────────────────────────────────────────────────


def mint_session_tokens(
    session: Session,
    users: list[tuple[uuid.UUID, str]],
) -> list[dict]:
    """Create one UserSession row per user, return harness-friendly tokens.

    Output list items: ``{"user_id": str, "username": str, "session_token": str}``.
    """
    out: list[dict] = []
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for uid, username in users:
        raw, token_hash = create_session_token()
        rows.append({
            "id": uuid.uuid4(),
            "user_id": uid,
            "token_hash": token_hash,
            "user_agent": "seed_load",
            "ip_address": "127.0.0.1",
            "created_at": now,
            "last_seen_at": now,
            "revoked_at": None,
        })
        out.append({
            "user_id": str(uid),
            "username": username,
            "session_token": raw,
        })
    if rows:
        session.execute(insert(UserSession), rows)
        session.commit()
    return out


# ── orchestration ────────────────────────────────────────────────────────────


def run(args: SeedArgs) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with Session(engine) as session:
        if args.reset:
            reset_loadtest(session)

        hashed_pw = get_password_hash(DEFAULT_PASSWORD)
        user_ids = seed_users(session, args.users, hashed_pw)
        if not user_ids:
            log.error("no users seeded — aborting")
            return

        owner_id = user_ids[0]
        rooms_map = seed_rooms(
            session,
            plain_rooms=args.rooms,
            big_room_size=args.big_room_size,
            history_room_size=args.history_room_size,
            owner_id=owner_id,
        )
        plain_room_ids = [
            rooms_map[f"{LOADTEST_PREFIX}room_{i}"] for i in range(args.rooms)
        ]
        big_room_id = rooms_map.get(f"{LOADTEST_PREFIX}bigroom")
        history_room_id = rooms_map.get(f"{LOADTEST_PREFIX}history")

        seed_memberships(
            session,
            plain_room_ids=plain_room_ids,
            members_per_room=args.members_per_room,
            big_room_id=big_room_id,
            big_room_size=args.big_room_size,
            history_room_id=history_room_id,
            history_room_size=args.history_room_size,
            user_ids=user_ids,
            owner_id=owner_id,
        )

        total_messages = 0
        for rid in plain_room_ids:
            total_messages += seed_messages(
                session, room_id=rid, author_ids=user_ids, count=args.messages,
            )
        if big_room_id is not None:
            total_messages += seed_messages(
                session,
                room_id=big_room_id,
                author_ids=user_ids[: max(1, args.big_room_size)],
                count=args.big_room_history,
            )
        if history_room_id is not None:
            total_messages += seed_messages(
                session,
                room_id=history_room_id,
                author_ids=user_ids[: max(1, args.history_room_size)],
                count=args.history_room_messages,
            )

        tokens: list[dict] = []
        if args.token_out is not None:
            # one token per user; harness picks whichever it needs
            username_by_id = {uid: f"{LOADTEST_PREFIX}{i}" for i, uid in enumerate(user_ids)}
            tokens = mint_session_tokens(
                session,
                [(uid, username_by_id[uid]) for uid in user_ids],
            )
            args.token_out.parent.mkdir(parents=True, exist_ok=True)
            args.token_out.write_text(json.dumps(tokens, indent=2))

    print(
        f"seeded: users={len(user_ids)} rooms={len(rooms_map)} "
        f"members_rooms={len(plain_room_ids)} messages={total_messages} "
        f"tokens={len(tokens)}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
