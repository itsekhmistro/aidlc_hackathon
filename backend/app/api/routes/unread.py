import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CookieCurrentUser, SessionDep
from app.schemas.message import UnreadCountsPublic

router = APIRouter(prefix="/api/unread", tags=["unread"])


@router.get("", response_model=UnreadCountsPublic)
def get_unread_counts(current_user: CookieCurrentUser, session: SessionDep) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{room_id}/mark-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_room_read(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
