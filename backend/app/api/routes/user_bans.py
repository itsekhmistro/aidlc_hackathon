import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CookieCurrentUser, SessionDep

router = APIRouter(prefix="/api/user-bans", tags=["user-bans"])


@router.get("", response_model=list[dict])
def list_user_bans(current_user: CookieCurrentUser, session: SessionDep) -> list:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def ban_user(user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
