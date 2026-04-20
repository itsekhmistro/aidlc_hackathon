import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.models.user import UserSession
from app.schemas.user import SessionPublic

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionPublic])
def list_sessions(current_user: CookieCurrentUser, session: SessionDep) -> list:
    rows = session.exec(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
    ).all()
    return list(rows)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    user_session = session.exec(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
        )
    ).first()
    if not user_session:
        raise HTTPException(status_code=404, detail="Session not found")
    user_session.revoked_at = datetime.now(timezone.utc)
    session.add(user_session)
    session.commit()
