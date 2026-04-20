import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CookieCurrentUser, SessionDep
from app.schemas.message import MessageCreate, MessagePage, MessagePublic, MessageUpdate

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("/{room_id}", response_model=MessagePage)
def list_messages(
    room_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
    before: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, le=100),
) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{room_id}", response_model=MessagePublic, status_code=status.HTTP_201_CREATED)
def send_message(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep, msg: MessageCreate) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/{room_id}/{message_id}", response_model=MessagePublic)
def edit_message(room_id: uuid.UUID, message_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep, msg: MessageUpdate) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{room_id}/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(room_id: uuid.UUID, message_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
