"""Prosody → FastAPI event webhook (TASK-13 §2.3).

Prosody posts one JSON body per S2S message or c2s session change to
``POST /api/internal/xmpp/event`` with an ``X-XMPP-Webhook-Token`` header.

Auth is shared-secret only — the backend is not reachable from outside the
compose network, and the session-cookie auth would be inappropriate here
(Prosody has no user session). The token lives in
``settings.XMPP_WEBHOOK_TOKEN`` and matches the value baked into Prosody's
config. Empty token in settings means the webhook is rejected (prevents
accidental wide-open deployments).

Payload discriminated on ``type``:
- ``federation.message`` → append a row to ``federation_log``.
- ``session.client``     → mutate the in-memory registry in ``xmpp_registry``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Header, HTTPException, status

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.xmpp_registry import (
    drop_s2s_peer,
    record_login,
    record_logout,
    record_s2s_peer,
)
from app.models.federation import FederationLog
from app.schemas.jabber import XmppEventEnvelope, XmppFederationEvent, XmppSessionEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/xmpp", tags=["xmpp-webhook"])


def _require_webhook_token(token: str | None) -> None:
    expected = settings.XMPP_WEBHOOK_TOKEN
    # Empty configured token = webhook is closed. Make this explicit so a
    # fresh deployment that forgets to set XMPP_WEBHOOK_TOKEN fails loud.
    if not expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook disabled")
    if not token or token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")


@router.post("/event", status_code=status.HTTP_204_NO_CONTENT)
def xmpp_event(
    session: SessionDep,
    event: XmppEventEnvelope = Body(...),
    x_xmpp_webhook_token: str | None = Header(default=None),
) -> None:
    _require_webhook_token(x_xmpp_webhook_token)

    if isinstance(event, XmppFederationEvent):
        preview = event.message_preview if settings.XMPP_LOG_PREVIEWS else None
        session.add(
            FederationLog(
                ts=event.ts,
                direction=event.direction,
                local_jid=event.local_jid,
                remote_jid=event.remote_jid,
                remote_server=event.remote_server,
                message_preview=preview,
                session_id=event.session_id,
            )
        )
        session.commit()
        # An S2S message implies the remote is an active peer — register it so
        # /status reports s2s_links_active > 0 even if Prosody hasn't emitted
        # a dedicated peer-established event.
        record_s2s_peer(event.remote_server)
        return

    if isinstance(event, XmppSessionEvent):
        if event.event == "login":
            record_login(
                event.jid,
                client=event.client,
                ip=event.ip,
                session_id=event.session_id,
            )
        else:
            record_logout(event.jid, session_id=event.session_id)
            # If this was the last session for a remote server, drop the peer.
            # We don't track that granularly; a noisy drop is better than a
            # phantom peer, so rely on the next federation.message to re-add.
            drop_s2s_peer(event.jid.split("@")[-1] if "@" in event.jid else event.jid)
        return

    # Pydantic discrimination should make this unreachable; log if it slips.
    logger.warning("xmpp webhook received unhandled event type=%s", getattr(event, "type", None))
