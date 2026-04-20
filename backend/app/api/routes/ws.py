import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

# Spec: specs/11-websocket-protocol.md:127 — reap silent clients after 90s.
IDLE_TIMEOUT = 90

from app.core.db import engine
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


def _upsert_presence(session: Session, user_id: uuid.UUID, status: str) -> None:
    presence = session.get(Presence, user_id)
    if presence:
        presence.status = status
        presence.updated_at = datetime.now(timezone.utc)
    else:
        presence = Presence(user_id=user_id, status=status)
    session.add(presence)
    session.commit()


# ── threadpool helpers ──────────────────────────────────────────────────
# WS endpoints are long-lived; holding a sync DB Session via Depends would
# pin a pool slot for the connection's lifetime. Instead, we offload every
# sync DB op to asyncio.to_thread so the event loop stays responsive and
# pool slots are released promptly. NFR 3.1 (300 concurrent) depends on
# this — without it the async loop stalls under the spawn stampede.


def _auth_sync(auth_token: str | None) -> uuid.UUID | None:
    with Session(engine) as s:
        user = _get_user_from_cookie(auth_token, s)
        return user.id if user else None


def _upsert_and_audience_sync(
    user_id: uuid.UUID, status: str
) -> set[uuid.UUID]:
    with Session(engine) as s:
        _upsert_presence(s, user_id, status)
        return presence_manager._get_audience(user_id, s)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    tab_id: str = Query(...),
    auth_token: str | None = Cookie(default=None),
) -> None:
    user_id = await asyncio.to_thread(_auth_sync, auth_token)
    if user_id is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    await presence_manager.connect(user_id, tab_id, websocket)

    audience = await asyncio.to_thread(_upsert_and_audience_sync, user_id, "online")
    if audience:
        event = {"type": "presence.update", "user_id": str(user_id), "status": "online"}
        await asyncio.gather(
            *(presence_manager.send_to_user(uid, event) for uid in audience),
            return_exceptions=True,
        )
    initial = [
        {"user_id": str(uid), "status": presence_manager.compute_status(uid)}
        for uid in audience
    ]
    await websocket.send_json({"type": "presence.bulk", "presences": initial})

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=IDLE_TIMEOUT
                )
            except asyncio.TimeoutError:
                await websocket.close(code=4000)
                break
            msg_type = data.get("type", "")

            if msg_type == "presence.heartbeat":
                new_status = await presence_manager.update_tab_status(
                    user_id, tab_id, data.get("status", "online")
                )
                if new_status is not None:
                    audience = await asyncio.to_thread(
                        _upsert_and_audience_sync, user_id, new_status
                    )
                    if audience:
                        event = {
                            "type": "presence.update",
                            "user_id": str(user_id),
                            "status": new_status,
                        }
                        await asyncio.gather(
                            *(presence_manager.send_to_user(uid, event) for uid in audience),
                            return_exceptions=True,
                        )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        new_status = await presence_manager.disconnect(user_id, tab_id)
        audience = await asyncio.to_thread(
            _upsert_and_audience_sync, user_id, new_status
        )
        if audience:
            event = {
                "type": "presence.update",
                "user_id": str(user_id),
                "status": new_status,
            }
            await asyncio.gather(
                *(presence_manager.send_to_user(uid, event) for uid in audience),
                return_exceptions=True,
            )
