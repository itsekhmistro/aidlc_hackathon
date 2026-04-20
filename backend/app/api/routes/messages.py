import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.core.social import ban_between
from app.models.message import Attachment, Message
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User
from app.schemas.message import (
    AttachmentPublic,
    MessageCreate,
    MessagePage,
    MessagePublic,
    MessageUpdate,
)

router = APIRouter(prefix="/api/rooms", tags=["messages"])


def _get_membership(session, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember | None:
    return session.exec(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
    ).first()


def _room_member_ids(session, room_id: uuid.UUID) -> set[uuid.UUID]:
    """Cached read-through to the ``room_member`` table."""
    return presence_manager.get_room_members(session, room_id)


async def _broadcast_room_event(session, room_id: uuid.UUID, event: dict[str, Any]) -> None:
    """Fan ``event`` out to every room member in parallel.

    ``send_to_user`` already swallows per-connection exceptions, so the
    ``return_exceptions=True`` here is belt-and-suspenders — guarantees a
    bug in one branch can never cancel the others.
    """
    member_ids = _room_member_ids(session, room_id)
    if not member_ids:
        return
    await asyncio.gather(
        *(presence_manager.send_to_user(uid, event) for uid in member_ids),
        return_exceptions=True,
    )


def _to_message_public(
    session,
    message: Message,
    *,
    client_msg_id: str | None = None,
) -> MessagePublic:
    author = session.get(User, message.author_id)
    attachments = session.exec(
        select(Attachment).where(Attachment.message_id == message.id)
    ).all()

    reply_preview: str | None = None
    if message.reply_to_id:
        reply_msg = session.get(Message, message.reply_to_id)
        if reply_msg and reply_msg.deleted_at is None:
            reply_preview = reply_msg.content[:100]

    return MessagePublic(
        id=message.id,
        room_id=message.room_id,
        author_id=message.author_id,
        author_username=author.username if author else "",
        content="" if message.deleted_at is not None else message.content,
        reply_to_id=message.reply_to_id,
        reply_preview=reply_preview,
        attachments=[
            AttachmentPublic(
                id=a.id,
                original_filename=a.original_filename,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                comment=a.comment,
                created_at=a.created_at,
            )
            for a in attachments
        ],
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted=message.deleted_at is not None,
        client_msg_id=client_msg_id,
    )


@router.get("/{room_id}/messages", response_model=MessagePage)
def list_messages(
    room_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
    before: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, le=100),
) -> dict:
    if not _get_membership(session, room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    q = select(Message).where(Message.room_id == room_id)

    if before:
        anchor = session.get(Message, before)
        if anchor:
            q = q.where(Message.created_at < anchor.created_at)

    q = q.order_by(Message.created_at.desc()).limit(limit + 1)  # type: ignore[attr-defined]
    rows = list(session.exec(q).all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = rows[-1].id if has_more and rows else None

    return MessagePage(
        messages=[_to_message_public(session, m) for m in rows],
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.post("/{room_id}/messages", response_model=MessagePublic, status_code=status.HTTP_201_CREATED)
async def send_message(
    room_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
    msg: MessageCreate,
) -> dict:
    if not _get_membership(session, room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room = session.get(Room, room_id)
    if room and room.is_personal:
        other_ids = [
            uid for uid in _room_member_ids(session, room_id) if uid != current_user.id
        ]
        if other_ids and ban_between(session, current_user.id, other_ids[0]):
            raise HTTPException(
                status_code=403,
                detail="Cannot send messages: user ban in effect",
            )

    message = Message(
        room_id=room_id,
        author_id=current_user.id,
        content=msg.content,
        reply_to_id=msg.reply_to_id,
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    if msg.attachment_ids:
        for att_id in msg.attachment_ids:
            att = session.get(Attachment, att_id)
            if att and att.uploaded_by_id == current_user.id and att.room_id == room_id and att.message_id is None:
                att.message_id = message.id
                session.add(att)
        session.commit()
        session.refresh(message)

    public = _to_message_public(session, message, client_msg_id=msg.client_msg_id)
    await _broadcast_room_event(
        session,
        room_id,
        {"type": "message.new", "room_id": str(room_id), "message": public.model_dump(mode="json")},
    )

    # unread.increment for every room member except the author — fan out in
    # parallel (TASK-16: 1000-member rooms would previously serialize this).
    unread_targets = [
        uid for uid in _room_member_ids(session, room_id) if uid != current_user.id
    ]
    if unread_targets:
        unread_event = {"type": "unread.increment", "room_id": str(room_id)}
        await asyncio.gather(
            *(presence_manager.send_to_user(uid, unread_event) for uid in unread_targets),
            return_exceptions=True,
        )

    return public


@router.patch("/{room_id}/messages/{message_id}", response_model=MessagePublic)
async def edit_message(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
    msg: MessageUpdate,
) -> dict:
    message = session.get(Message, message_id)
    if not message or message.room_id != room_id:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit this message")

    room = session.get(Room, room_id)
    if room and room.is_personal:
        other_ids = [
            uid for uid in _room_member_ids(session, room_id) if uid != current_user.id
        ]
        if other_ids and ban_between(session, current_user.id, other_ids[0]):
            raise HTTPException(
                status_code=403,
                detail="Cannot edit messages: user ban in effect",
            )

    message.content = msg.content
    message.edited_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
    session.refresh(message)

    public = _to_message_public(session, message)
    await _broadcast_room_event(
        session,
        room_id,
        {"type": "message.edited", "message": public.model_dump(mode="json")},
    )

    return public


@router.delete("/{room_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> None:
    message = session.get(Message, message_id)
    if not message or message.room_id != room_id:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.author_id != current_user.id:
        membership = _get_membership(session, room_id, current_user.id)
        if not membership or membership.role not in (
            MemberRole.owner.value,
            MemberRole.admin.value,
        ):
            raise HTTPException(
                status_code=403,
                detail="Only the author or a room admin can delete this message",
            )

    message.deleted_at = datetime.now(timezone.utc)
    message.content = ""
    session.add(message)
    session.commit()

    await _broadcast_room_event(
        session,
        room_id,
        {
            "type": "message.deleted",
            "message_id": str(message_id),
            "room_id": str(room_id),
        },
    )
