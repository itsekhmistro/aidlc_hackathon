import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.presence import presence_manager
from app.models.user import Presence, User, UserSession

router = APIRouter()


def _get_user_from_cookie(token: str | None, session: Session) -> User | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user_session = session.exec(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if not user_session:
        return None
    user = session.get(User, user_session.user_id)
    if not user or user.deleted_at is not None:
        return None
    return user


def _upsert_presence(session: Session, user_id, status: str) -> None:
    presence = session.get(Presence, user_id)
    if presence:
        presence.status = status
        presence.updated_at = datetime.now(timezone.utc)
    else:
        presence = Presence(user_id=user_id, status=status)
    session.add(presence)
    session.commit()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    tab_id: str = Query(...),
    auth_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> None:
    user = _get_user_from_cookie(auth_token, session)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    await presence_manager.connect(user.id, tab_id, websocket)
    _upsert_presence(session, user.id, "online")
    await presence_manager.broadcast_presence(user.id, "online", session)

    initial = await presence_manager.get_initial_presences(user.id, session)
    await websocket.send_json({"type": "presence.bulk", "presences": initial})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "presence.heartbeat":
                new_status = await presence_manager.update_tab_status(
                    user.id, tab_id, data.get("status", "online")
                )
                if new_status is not None:
                    _upsert_presence(session, user.id, new_status)
                    await presence_manager.broadcast_presence(user.id, new_status, session)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        new_status = await presence_manager.disconnect(user.id, tab_id)
        _upsert_presence(session, user.id, new_status)
        await presence_manager.broadcast_presence(user.id, new_status, session)
