import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class RoomVisibility(str, Enum):
    public = "public"
    private = "private"


class MemberRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class Room(SQLModel, table=True):
    __tablename__ = "room"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    visibility: str = Field(default=RoomVisibility.public.value, max_length=20)
    owner_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    is_personal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomMember(SQLModel, table=True):
    __tablename__ = "room_member"

    room_id: uuid.UUID = Field(foreign_key="room.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    role: str = Field(default=MemberRole.member.value, max_length=20)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomBan(SQLModel, table=True):
    __tablename__ = "room_ban"

    room_id: uuid.UUID = Field(foreign_key="room.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    # banned_by_id deliberately uses sa_column to avoid FK ambiguity warning
    banned_by_id: uuid.UUID = Field(foreign_key="user.id")
    banned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomInvitation(SQLModel, table=True):
    __tablename__ = "room_invitation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    room_id: uuid.UUID = Field(foreign_key="room.id", index=True)
    invited_by_id: uuid.UUID = Field(foreign_key="user.id")
    invited_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: datetime | None = Field(default=None)
