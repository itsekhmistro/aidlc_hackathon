import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.api.routes.rooms import _to_room_public
from app.core.social import ban_between, friendship_between
from app.models.room import MemberRole, Room, RoomMember, RoomVisibility
from app.models.social import FriendshipStatus
from app.models.user import User
from app.schemas.room import RoomPublic

router = APIRouter(prefix="/api/personal-rooms", tags=["personal-rooms"])


@router.get("/{user_id}", response_model=RoomPublic)
async def get_or_create_personal_room(
    user_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> dict:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create a DM room with yourself")

    target = session.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    if ban_between(session, current_user.id, user_id):
        raise HTTPException(status_code=403, detail="Cannot create DM: ban exists between users")

    friendship = friendship_between(session, current_user.id, user_id)
    if not friendship or friendship.status != FriendshipStatus.accepted.value:
        raise HTTPException(status_code=403, detail="Cannot create DM: users are not friends")

    dm_name = f"__dm__:{':'.join(sorted([str(current_user.id), str(user_id)]))}"

    room = session.exec(select(Room).where(Room.name == dm_name)).first()
    if not room:
        room = Room(
            name=dm_name,
            visibility=RoomVisibility.private.value,
            owner_id=current_user.id,
            is_personal=True,
        )
        session.add(room)
        session.flush()

        session.add(RoomMember(room_id=room.id, user_id=current_user.id, role=MemberRole.owner.value))
        session.add(RoomMember(room_id=room.id, user_id=user_id, role=MemberRole.member.value))
        session.commit()
        session.refresh(room)

    return _to_room_public(session, room, current_user.id)
