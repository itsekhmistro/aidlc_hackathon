import uuid
from datetime import datetime

from sqlmodel import SQLModel


class AttachmentPublic(SQLModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    comment: str | None
    created_at: datetime


class MessagePublic(SQLModel):
    id: uuid.UUID
    room_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content: str
    reply_to_id: uuid.UUID | None
    reply_preview: str | None = None
    attachments: list[AttachmentPublic] = []
    created_at: datetime
    edited_at: datetime | None
    deleted: bool = False


class MessageCreate(SQLModel):
    content: str
    reply_to_id: uuid.UUID | None = None


class MessageUpdate(SQLModel):
    content: str


class MessagePage(SQLModel):
    messages: list[MessagePublic]
    has_more: bool
    next_cursor: uuid.UUID | None


class UnreadCountsPublic(SQLModel):
    counts: dict[str, int]  # room_id (str) → unread count
