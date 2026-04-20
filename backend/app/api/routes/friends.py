import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.core.social import ban_between, friendship_between
from app.models.social import Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.social import FriendRequestCreate, FriendshipPublic

router = APIRouter(prefix="/api/friends", tags=["friends"])


def _to_friendship_public(session, friendship: Friendship) -> FriendshipPublic:
    requester = session.get(User, friendship.requester_id)
    addressee = session.get(User, friendship.addressee_id)
    return FriendshipPublic(
        id=friendship.id,
        requester_id=friendship.requester_id,
        requester_username=requester.username if requester else "",
        addressee_id=friendship.addressee_id,
        addressee_username=addressee.username if addressee else "",
        status=friendship.status,
        message=friendship.message,
        created_at=friendship.created_at,
        updated_at=friendship.updated_at,
    )


@router.post("/request", response_model=FriendshipPublic, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    current_user: CookieCurrentUser,
    session: SessionDep,
    body: FriendRequestCreate,
) -> dict:
    # Resolve target user by username
    target = session.exec(
        select(User).where(User.username == body.username, User.deleted_at.is_(None))  # type: ignore[attr-defined]
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # 400 if requesting yourself
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")

    # 400 if ban exists (either direction)
    if ban_between(session, current_user.id, target.id):
        raise HTTPException(status_code=400, detail="Cannot send friend request: ban exists")

    # 409 if friendship already exists (any status)
    if friendship_between(session, current_user.id, target.id):
        raise HTTPException(status_code=409, detail="Friendship already exists")

    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=target.id,
        status=FriendshipStatus.pending.value,
        message=body.message,
    )
    session.add(friendship)
    session.commit()
    session.refresh(friendship)

    public = _to_friendship_public(session, friendship)
    await presence_manager.send_to_user(
        target.id,
        {"type": "friend.request_received", "friendship": public.model_dump(mode="json")},
    )

    return public


@router.get("", response_model=list[FriendshipPublic])
def list_friends(current_user: CookieCurrentUser, session: SessionDep) -> list:
    friendships = session.exec(
        select(Friendship).where(
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.addressee_id == current_user.id,
            ),
            Friendship.status == FriendshipStatus.accepted.value,
        )
    ).all()
    return [_to_friendship_public(session, f) for f in friendships]


@router.get("/requests/incoming", response_model=list[FriendshipPublic])
def incoming_requests(current_user: CookieCurrentUser, session: SessionDep) -> list:
    friendships = session.exec(
        select(Friendship).where(
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.pending.value,
        )
    ).all()
    return [_to_friendship_public(session, f) for f in friendships]


@router.patch("/{friendship_id}/accept", response_model=FriendshipPublic)
async def accept_friend_request(
    friendship_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> dict:
    friendship = session.get(Friendship, friendship_id)
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship not found")
    if friendship.addressee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the addressee can accept this request")

    from datetime import datetime, timezone
    friendship.status = FriendshipStatus.accepted.value
    friendship.updated_at = datetime.now(timezone.utc)
    session.add(friendship)
    session.commit()
    session.refresh(friendship)

    public = _to_friendship_public(session, friendship)
    await presence_manager.send_to_user(
        friendship.requester_id,
        {"type": "friend.request_accepted", "friendship": public.model_dump(mode="json")},
    )

    return public


@router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friendship_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> None:
    friendship = session.get(Friendship, friendship_id)
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship not found")
    if friendship.requester_id != current_user.id and friendship.addressee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not a participant of this friendship")

    other_id = (
        friendship.addressee_id
        if friendship.requester_id == current_user.id
        else friendship.requester_id
    )

    session.delete(friendship)
    session.commit()

    await presence_manager.send_to_user(
        other_id,
        {"type": "friend.removed", "friendship_id": str(friendship_id)},
    )
