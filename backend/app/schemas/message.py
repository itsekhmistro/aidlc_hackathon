import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


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
    # TASK-16: harness-supplied correlation id, echoed through the live WS
    # broadcast so the load-test harness can compute e2e latency. Never
    # persisted — always None for history reads.
    client_msg_id: str | None = None


class MessageCreate(SQLModel):
    content: str
    reply_to_id: uuid.UUID | None = None
    attachment_ids: list[uuid.UUID] = []
    # TASK-16: optional client-generated correlation id (<= 64 chars).
    # Pass-through only — not persisted to the DB.
    client_msg_id: str | None = Field(default=None, max_length=64)


class MessageUpdate(SQLModel):
    content: str


class MessagePage(SQLModel):
    messages: list[MessagePublic]
    has_more: bool
    next_cursor: uuid.UUID | None


class UnreadCountsPublic(SQLModel):
    counts: dict[str, int]  # room_id (str) → unread count
