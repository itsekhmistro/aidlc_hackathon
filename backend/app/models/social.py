import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class FriendshipStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"


class Friendship(SQLModel, table=True):
    __tablename__ = "friendship"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    requester_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    addressee_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    status: str = Field(default=FriendshipStatus.pending.value, max_length=20)
    message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserBan(SQLModel, table=True):
    __tablename__ = "user_ban"

    banner_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    banned_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
