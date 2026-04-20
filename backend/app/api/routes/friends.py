import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CookieCurrentUser, SessionDep
from app.schemas.social import FriendRequestCreate, FriendshipPublic

router = APIRouter(prefix="/api/friends", tags=["friends"])


@router.get("", response_model=list[FriendshipPublic])
def list_friends(current_user: CookieCurrentUser, session: SessionDep) -> list:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/requests/incoming", response_model=list[FriendshipPublic])
def incoming_requests(current_user: CookieCurrentUser, session: SessionDep) -> list:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/request", response_model=FriendshipPublic, status_code=status.HTTP_201_CREATED)
def send_friend_request(current_user: CookieCurrentUser, session: SessionDep, body: FriendRequestCreate) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/{friendship_id}/accept", response_model=FriendshipPublic)
def accept_friend_request(friendship_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(friendship_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
