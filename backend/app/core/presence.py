import uuid
from collections import defaultdict

from fastapi import WebSocket
from sqlmodel import Session, or_, select


class PresenceManager:
    def __init__(self) -> None:
        self.connections: dict[uuid.UUID, dict[str, WebSocket]] = defaultdict(dict)
        self.tab_status: dict[str, str] = {}

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
        for ws in list(self.connections.get(user_id, {}).values()):
            try:
                await ws.send_json(event)
            except Exception:
                pass

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
        for uid in self._get_audience(user_id, session):
            await self.send_to_user(uid, event)

    async def get_initial_presences(self, user_id: uuid.UUID, session: Session) -> list[dict]:
        return [
            {"user_id": str(uid), "status": self.compute_status(uid)}
            for uid in self._get_audience(user_id, session)
        ]


presence_manager = PresenceManager()
