import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.models.message import Message, ReadReceipt
from app.models.room import RoomMember
from app.schemas.message import UnreadCountsPublic

router = APIRouter(prefix="/api/unread", tags=["unread"])


@router.get("", response_model=UnreadCountsPublic)
def get_unread_counts(current_user: CookieCurrentUser, session: SessionDep) -> dict:
    LastRead = aliased(Message)
    stmt = (
        select(RoomMember.room_id, func.count(Message.id))
        .select_from(RoomMember)
        .outerjoin(
            ReadReceipt,
            (ReadReceipt.room_id == RoomMember.room_id)
            & (ReadReceipt.user_id == RoomMember.user_id),
        )
        .outerjoin(LastRead, LastRead.id == ReadReceipt.last_read_message_id)
        .outerjoin(
            Message,
            (Message.room_id == RoomMember.room_id)
            & Message.deleted_at.is_(None)
            & (Message.author_id != current_user.id)
            & LastRead.created_at.isnot(None)
            & (Message.created_at > LastRead.created_at),
        )
        .where(RoomMember.user_id == current_user.id)
        .group_by(RoomMember.room_id)
    )
    rows = session.exec(stmt).all()
    counts = {str(rid): int(cnt) for rid, cnt in rows}
    return UnreadCountsPublic(counts=counts)


@router.post("/{room_id}/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_room_read(
    room_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> None:
    membership = session.exec(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == current_user.id)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    latest = session.exec(
        select(Message)
        .where(Message.room_id == room_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
    ).first()
    if latest is None:
        return

    receipt = session.exec(
        select(ReadReceipt).where(ReadReceipt.room_id == room_id, ReadReceipt.user_id == current_user.id)
    ).first()
    if receipt:
        receipt.last_read_message_id = latest.id
        receipt.updated_at = datetime.now(timezone.utc)
    else:
        receipt = ReadReceipt(
            room_id=room_id,
            user_id=current_user.id,
            last_read_message_id=latest.id,
        )
    session.add(receipt)
    session.commit()

    await presence_manager.send_to_user(
        current_user.id,
        {"type": "unread.cleared", "room_id": str(room_id)},
    )
