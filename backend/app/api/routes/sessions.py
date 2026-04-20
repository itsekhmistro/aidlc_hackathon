import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.models.user import UserSession
from app.schemas.user import SessionPublic

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionPublic])
def list_sessions(
    current_user: CookieCurrentUser,
    session: SessionDep,
    request: Request,
) -> list[SessionPublic]:
    rows = session.exec(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
    ).all()

    # Hash the caller's cookie with the same scheme the auth layer uses
    # (see app.core.security.create_session_token: sha256 of the raw token).
    raw_token = request.cookies.get("auth_token")
    current_hash = (
        hashlib.sha256(raw_token.encode()).hexdigest() if raw_token else None
    )

    return [
        SessionPublic(
            id=row.id,
            user_agent=row.user_agent,
            ip_address=row.ip_address,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            is_current=(current_hash is not None and row.token_hash == current_hash),
        )
        for row in rows
    ]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
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

    await presence_manager.send_to_user(
        current_user.id,
        {"type": "session.revoked", "session_id": str(session_id)},
    )
