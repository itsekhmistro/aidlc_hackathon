import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.models.message import Message, ReadReceipt
from app.models.room import RoomMember
from app.schemas.message import UnreadCountsPublic

router = APIRouter(prefix="/api/unread", tags=["unread"])


@router.get("", response_model=UnreadCountsPublic)
def get_unread_counts(current_user: CookieCurrentUser, session: SessionDep) -> dict:
    room_ids = session.exec(
        select(RoomMember.room_id).where(RoomMember.user_id == current_user.id)
    ).all()

    counts: dict[str, int] = {}
    for room_id in room_ids:
        receipt = session.exec(
            select(ReadReceipt).where(
                ReadReceipt.room_id == room_id,
                ReadReceipt.user_id == current_user.id,
            )
        ).first()
        if receipt is None:
            counts[str(room_id)] = 0
        else:
            last_msg = session.get(Message, receipt.last_read_message_id)
            if last_msg is None:
                counts[str(room_id)] = 0
            else:
                count = session.exec(
                    select(func.count()).select_from(Message).where(
                        Message.room_id == room_id,
                        Message.created_at > last_msg.created_at,
                        Message.deleted_at.is_(None),
                    )
                ).one()
                counts[str(room_id)] = count

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
