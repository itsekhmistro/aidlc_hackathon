import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import CookieCurrentUser, SessionDep
from app.schemas.room import RoomPublic

router = APIRouter(prefix="/api/personal-rooms", tags=["personal-rooms"])


@router.get("/{user_id}", response_model=RoomPublic)
def get_or_create_personal_room(user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")
