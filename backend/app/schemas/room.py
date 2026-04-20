import uuid
from datetime import datetime

from sqlmodel import SQLModel

from app.models.room import MemberRole, RoomVisibility


class RoomPublic(SQLModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: str | None
    visibility: str
    owner_id: uuid.UUID
    is_personal: bool
    created_at: datetime
    member_count: int = 0


class RoomCreate(SQLModel):
    name: str
    description: str | None = None
    visibility: RoomVisibility = RoomVisibility.public


class RoomUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    visibility: RoomVisibility | None = None


class RoomMemberPublic(SQLModel):
    user_id: uuid.UUID
    username: str
    role: str
    presence_status: str = "offline"
    joined_at: datetime


class RoomBanPublic(SQLModel):
    user_id: uuid.UUID
    username: str
    banned_by_id: uuid.UUID
    banned_by_username: str
    banned_at: datetime


class RoomInvitationPublic(SQLModel):
    id: uuid.UUID
    room_id: uuid.UUID
    invited_by_id: uuid.UUID
    invited_user_id: uuid.UUID
    created_at: datetime
    accepted_at: datetime | None


class InviteUserRequest(SQLModel):
    username: str


class AdminActionRequest(SQLModel):
    user_id: uuid.UUID
