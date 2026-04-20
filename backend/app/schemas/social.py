import uuid
from datetime import datetime

from sqlmodel import SQLModel


class FriendshipPublic(SQLModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    requester_username: str
    addressee_id: uuid.UUID
    addressee_username: str
    status: str
    message: str | None
    created_at: datetime
    updated_at: datetime


class FriendRequestCreate(SQLModel):
    username: str
    message: str | None = None


class UserBanPublic(SQLModel):
    banner_id: uuid.UUID
    banned_id: uuid.UUID
    created_at: datetime


class PresenceBulkRequest(SQLModel):
    user_ids: list[uuid.UUID]


class PresenceBulkResponse(SQLModel):
    presences: dict[str, str]  # user_id (str) → status
