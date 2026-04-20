import hashlib
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.config import settings
from app.core.security import create_session_token, get_password_hash, verify_password
from app.models.message import Attachment, Message, ReadReceipt
from app.models.room import Room, RoomBan, RoomInvitation, RoomMember
from app.models.social import Friendship, UserBan
from app.models.user import Presence, User, UserSession
from app.schemas.user import (
    LoginRequest,
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    UserCreate,
    UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserPublic)
def get_me(current_user: CookieCurrentUser) -> User:
    return current_user


def _create_session_cookie(
    db: object,
    response: Response,
    user: User,
    user_agent: str | None,
    ip_address: str | None,
    persistent: bool,
) -> None:
    from sqlmodel import Session as DBSession

    raw, token_hash = create_session_token()
    user_session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(user_session)  # type: ignore[attr-defined]
    db.commit()  # type: ignore[attr-defined]

    kwargs: dict = {"httponly": True, "samesite": "lax", "path": "/"}
    if persistent:
        kwargs["max_age"] = 2_592_000  # 30 days
    response.set_cookie("auth_token", raw, **kwargs)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(session: SessionDep, user_in: UserCreate, response: Response, request: Request) -> User:
    # Username is a permanent tombstone — check across all users including deleted
    if session.exec(select(User).where(User.username == user_in.username)).first():
        raise HTTPException(status_code=422, detail="Username already taken")
    if session.exec(
        select(User).where(User.email == user_in.email, User.deleted_at.is_(None))  # type: ignore[attr-defined]
    ).first():
        raise HTTPException(status_code=422, detail="Email already registered")

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    _create_session_cookie(
        session,
        response,
        user,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
        False,
    )
    return user


@router.post("/login", response_model=UserPublic)
def login(session: SessionDep, login_in: LoginRequest, response: Response, request: Request) -> User:
    user = session.exec(
        select(User).where(User.email == login_in.email, User.deleted_at.is_(None))  # type: ignore[attr-defined]
    ).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _create_session_cookie(
        session,
        response,
        user,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
        login_in.persistent,
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: CookieCurrentUser,
    session: SessionDep,
    response: Response,
    auth_token: str | None = Cookie(default=None),
) -> None:
    if auth_token:
        token_hash = hashlib.sha256(auth_token.encode()).hexdigest()
        user_session = session.exec(
            select(UserSession).where(UserSession.token_hash == token_hash)
        ).first()
        if user_session:
            user_session.revoked_at = datetime.now(timezone.utc)
            session.add(user_session)
            session.commit()
    response.delete_cookie("auth_token", path="/")


@router.post("/password-reset-request", status_code=status.HTTP_200_OK)
def password_reset_request(session: SessionDep, body: PasswordResetRequest) -> dict:
    user = session.exec(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))  # type: ignore[attr-defined]
    ).first()
    if not user:
        # Don't reveal whether email exists
        return {"message": "If the email is registered, a reset token has been issued"}

    raw, token_hash = create_session_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash,
            user_agent="password_reset",
        )
    )
    session.commit()
    return {"reset_token": raw}


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def password_reset(session: SessionDep, body: PasswordReset) -> None:
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    reset_session = session.exec(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.user_agent == "password_reset",
            UserSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if not reset_session:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = session.get(User, reset_session.user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(body.new_password)
    reset_session.revoked_at = datetime.now(timezone.utc)
    session.add(user)
    session.add(reset_session)
    session.commit()


@router.patch("/password-change", status_code=status.HTTP_204_NO_CONTENT)
def password_change(current_user: CookieCurrentUser, session: SessionDep, body: PasswordChange) -> None:
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    current_user.hashed_password = get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(current_user: CookieCurrentUser, session: SessionDep, response: Response) -> None:
    uid = current_user.id
    rooms_to_remove: list[str] = []

    # 1. Cascade-delete owned rooms
    owned_rooms = session.exec(select(Room).where(Room.owner_id == uid)).all()
    for room in owned_rooms:
        # Delete read receipts first (references message.id + room.id)
        for rr in session.exec(select(ReadReceipt).where(ReadReceipt.room_id == room.id)).all():
            session.delete(rr)

        # Delete attachments then messages
        msgs = session.exec(select(Message).where(Message.room_id == room.id)).all()
        for msg in msgs:
            for att in session.exec(select(Attachment).where(Attachment.message_id == msg.id)).all():
                session.delete(att)
        for msg in msgs:
            session.delete(msg)

        for row in session.exec(select(RoomMember).where(RoomMember.room_id == room.id)).all():
            session.delete(row)
        for row in session.exec(select(RoomBan).where(RoomBan.room_id == room.id)).all():
            session.delete(row)
        for row in session.exec(select(RoomInvitation).where(RoomInvitation.room_id == room.id)).all():
            session.delete(row)

        rooms_to_remove.append(str(room.id))
        session.delete(room)

    # 2. Remove membership from non-owned rooms
    for row in session.exec(select(RoomMember).where(RoomMember.user_id == uid)).all():
        session.delete(row)

    # 3. Clean up pending invitations addressed to this user
    for row in session.exec(select(RoomInvitation).where(RoomInvitation.invited_user_id == uid)).all():
        session.delete(row)

    # 4. Clean up read receipts in non-owned rooms
    for row in session.exec(select(ReadReceipt).where(ReadReceipt.user_id == uid)).all():
        session.delete(row)

    # 5. Friendships + user bans
    for row in session.exec(
        select(Friendship).where(or_(Friendship.requester_id == uid, Friendship.addressee_id == uid))
    ).all():
        session.delete(row)
    for row in session.exec(
        select(UserBan).where(or_(UserBan.banner_id == uid, UserBan.banned_id == uid))
    ).all():
        session.delete(row)

    # 6. Presence record
    presence = session.get(Presence, uid)
    if presence:
        session.delete(presence)

    # 7. Revoke all sessions
    for row in session.exec(select(UserSession).where(UserSession.user_id == uid)).all():
        session.delete(row)

    # 8. Soft-delete user (tombstone preserves username)
    current_user.deleted_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()

    # 9. Remove uploaded files from disk (after commit so DB is consistent)
    for room_id_str in rooms_to_remove:
        shutil.rmtree(os.path.join(settings.UPLOAD_DIR, room_id_str), ignore_errors=True)

    response.delete_cookie("auth_token", path="/")
