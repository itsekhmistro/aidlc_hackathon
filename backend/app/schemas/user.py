import uuid
from datetime import datetime

from sqlmodel import SQLModel


class UserPublic(SQLModel):
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime


class UserCreate(SQLModel):
    username: str
    email: str
    password: str


class UserUpdate(SQLModel):
    email: str | None = None
    password: str | None = None


class SessionPublic(SQLModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_seen_at: datetime


class PasswordResetRequest(SQLModel):
    email: str


class PasswordReset(SQLModel):
    token: str
    new_password: str


class PasswordChange(SQLModel):
    old_password: str
    new_password: str


class LoginRequest(SQLModel):
    email: str
    password: str
    persistent: bool = False
