import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class PresenceStatus(str, Enum):
    online = "online"
    afk = "afk"
    offline = "offline"


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = Field(default=None)


class UserSession(SQLModel, table=True):
    __tablename__ = "user_session"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(unique=True, index=True, max_length=64)
    user_agent: str | None = Field(default=None, max_length=500)
    ip_address: str | None = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = Field(default=None)


class Presence(SQLModel, table=True):
    __tablename__ = "presence"

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    status: str = Field(default=PresenceStatus.offline.value, max_length=20)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
