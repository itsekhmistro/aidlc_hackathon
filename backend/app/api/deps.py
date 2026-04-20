import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine, get_session
from app.core.security import ALGORITHM
from app.models.user import User, UserSession
from app.schemas.token import TokenPayload

SessionDep = Annotated[Session, Depends(get_session)]


# ── Cookie-based session auth (new) ──────────────────────────────────────────

def get_current_user_cookie(
    session: SessionDep,
    auth_token: str | None = Cookie(default=None),
) -> User:
    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_hash = hashlib.sha256(auth_token.encode()).hexdigest()
    user_session = session.exec(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if not user_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")
    user = session.get(User, user_session.user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    user_session.last_seen_at = datetime.now(timezone.utc)
    session.add(user_session)
    session.commit()
    return user


CookieCurrentUser = Annotated[User, Depends(get_current_user_cookie)]


# ── Legacy JWT auth (kept for existing login.py / users.py) ──────────────────

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")
    if not token_data.sub:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    user = session.get(User, uuid.UUID(token_data.sub))
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    return current_user
