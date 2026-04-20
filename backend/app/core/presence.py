import asyncio
import uuid
from collections import defaultdict

from fastapi import WebSocket
from sqlmodel import Session, or_, select


class PresenceManager:
    def __init__(self) -> None:
        self.connections: dict[uuid.UUID, dict[str, WebSocket]] = defaultdict(dict)
        self.tab_status: dict[str, str] = {}
        # Room-member cache: room_id -> set of user_ids. Populated lazily on
        # first read, invalidated via invalidate_room() on join/leave/ban/delete.
        # Scope: single-process only. If we ever scale horizontally this must
        # move to Redis pub/sub (out of scope for TASK-16).
        self._room_members: dict[uuid.UUID, set[uuid.UUID]] = {}

    def compute_status(self, user_id: uuid.UUID) -> str:
        tabs = self.connections.get(user_id, {})
        if not tabs:
            return "offline"
        if any(self.tab_status.get(tid) == "online" for tid in tabs):
            return "online"
        return "afk"

    async def connect(self, user_id: uuid.UUID, tab_id: str, ws: WebSocket) -> None:
        self.connections[user_id][tab_id] = ws
        self.tab_status[tab_id] = "online"

    async def disconnect(self, user_id: uuid.UUID, tab_id: str) -> str:
        self.connections[user_id].pop(tab_id, None)
        self.tab_status.pop(tab_id, None)
        if not self.connections[user_id]:
            del self.connections[user_id]
        return self.compute_status(user_id)

    async def update_tab_status(self, user_id: uuid.UUID, tab_id: str, status: str) -> str | None:
        old = self.compute_status(user_id)
        self.tab_status[tab_id] = status
        new = self.compute_status(user_id)
        return new if old != new else None

    async def send_to_user(self, user_id: uuid.UUID, event: dict) -> None:
        """Send to every live tab in parallel.

        One dead socket must not sink the others, so we gather with
        return_exceptions=True and drop failures silently (matches the pre-
        gather behavior of the per-tab try/except swallow).
        """
        sockets = list(self.connections.get(user_id, {}).values())
        if not sockets:
            return
        await asyncio.gather(
            *(ws.send_json(event) for ws in sockets),
            return_exceptions=True,
        )

    def _get_audience(self, user_id: uuid.UUID, session: Session) -> set[uuid.UUID]:
        from app.models.room import RoomMember
        from app.models.social import Friendship

        my_rooms = session.exec(
            select(RoomMember.room_id).where(RoomMember.user_id == user_id)
        ).all()

        audience: set[uuid.UUID] = set()
        if my_rooms:
            mates = session.exec(
                select(RoomMember.user_id).where(
                    RoomMember.room_id.in_(my_rooms),
                    RoomMember.user_id != user_id,
                )
            ).all()
            audience.update(mates)

        friends = session.exec(
            select(Friendship).where(
                or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
                Friendship.status == "accepted",
            )
        ).all()
        for f in friends:
            other = f.addressee_id if f.requester_id == user_id else f.requester_id
            audience.add(other)

        return audience

    async def broadcast_presence(self, user_id: uuid.UUID, status: str, session: Session) -> None:
        event = {"type": "presence.update", "user_id": str(user_id), "status": status}
        audience = self._get_audience(user_id, session)
        if not audience:
            return
        await asyncio.gather(
            *(self.send_to_user(uid, event) for uid in audience),
            return_exceptions=True,
        )

    async def get_initial_presences(self, user_id: uuid.UUID, session: Session) -> list[dict]:
        return [
            {"user_id": str(uid), "status": self.compute_status(uid)}
            for uid in self._get_audience(user_id, session)
        ]

    # ── room-member cache (TASK-16) ──────────────────────────────────────────

    def get_room_members(self, session: Session, room_id: uuid.UUID) -> set[uuid.UUID]:
        """Return the set of user_ids that belong to this room.

        Cached in memory; first miss populates from a single
        ``SELECT user_id FROM room_member WHERE room_id = :room_id``. Callers
        that mutate membership MUST invoke :meth:`invalidate_room`.
        """
        cached = self._room_members.get(room_id)
        if cached is not None:
            return cached

        from app.models.room import RoomMember

        rows = session.exec(
            select(RoomMember.user_id).where(RoomMember.room_id == room_id)
        ).all()
        members = set(rows)
        self._room_members[room_id] = members
        return members

    def invalidate_room(self, room_id: uuid.UUID) -> None:
        """Drop the cached member set for ``room_id``.

        Call from join / leave / ban / unban / kick / admin-delete /
        room-delete handlers — anywhere a RoomMember row is inserted or
        removed. Safe to call even if the entry was never cached.
        """
        self._room_members.pop(room_id, None)


presence_manager = PresenceManager()
