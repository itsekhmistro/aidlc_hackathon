import uuid
from datetime import datetime, timezone

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "message"
    __table_args__ = (
        Index("ix_message_room_created", "room_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    room_id: uuid.UUID = Field(foreign_key="room.id", index=True)
    author_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    content: str = Field(max_length=3072)
    reply_to_id: uuid.UUID | None = Field(default=None, foreign_key="message.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    edited_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)


class Attachment(SQLModel, table=True):
    __tablename__ = "attachment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    message_id: uuid.UUID | None = Field(default=None, foreign_key="message.id", index=True)
    room_id: uuid.UUID = Field(foreign_key="room.id", index=True)
    original_filename: str = Field(max_length=255)
    stored_path: str = Field(max_length=1000)
    mime_type: str = Field(max_length=100)
    size_bytes: int
    comment: str | None = Field(default=None, max_length=500)
    uploaded_by_id: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadReceipt(SQLModel, table=True):
    __tablename__ = "read_receipt"
    __table_args__ = (
        Index("ix_read_receipt_user_id", "user_id"),
    )

    room_id: uuid.UUID = Field(foreign_key="room.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    last_read_message_id: uuid.UUID = Field(foreign_key="message.id")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
