"""Admin-only read endpoints for the Jabber dashboards (TASK-13 §2.1, §2.2).

``GET /api/admin/jabber/status``     — server liveness + c2s session list.
``GET /api/admin/jabber/federation`` — S2S remotes + recent message log.

Both require ``is_admin=True`` on the caller. The dep surface below is the
one place we enforce the flag — every admin feature should depend on
``require_admin`` rather than re-implementing the 403 check.

Data sources:
- c2s sessions live in an in-memory registry populated by the Prosody webhook
  (``app.core.xmpp_registry``). No DB round-trip — the dashboard polls every
  10 s and missing a session for up to that long is acceptable.
- Federation traffic is aggregated from ``federation_log`` (SQL GROUP BY on
  remote_server + MAX(ts); recent = last 50 rows by ts desc).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.config import settings
from app.core.xmpp_registry import (
    SESSIONS_TRUNCATE_AT,
    get_process_start_monotonic,
    list_sessions_snapshot,
    s2s_peer_count,
)
from app.models.federation import FederationLog
from app.models.user import User
from app.schemas.jabber import (
    JabberFederation,
    JabberFederationMessage,
    JabberFederationRemote,
    JabberSession,
    JabberStatus,
)


def require_admin(current_user: CookieCurrentUser) -> User:
    """Auth dep — 403s non-admins.

    Registered as a FastAPI ``Depends`` rather than a function call so the
    404-if-not-found / 401-if-not-logged-in paths from ``CookieCurrentUser``
    layer cleanly underneath.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]


router = APIRouter(prefix="/api/admin/jabber", tags=["admin-jabber"])


@router.get("/status", response_model=JabberStatus)
def jabber_status(_: AdminUser) -> JabberStatus:
    sessions_full = list_sessions_snapshot()
    truncated = len(sessions_full) > SESSIONS_TRUNCATE_AT
    sessions = sessions_full[:SESSIONS_TRUNCATE_AT]

    now = time.monotonic()
    uptime = int(now - get_process_start_monotonic())

    return JabberStatus(
        server_host=settings.XMPP_DOMAIN,
        uptime_seconds=max(uptime, 0),
        connected_clients=len(sessions_full),
        s2s_links_active=s2s_peer_count(),
        sessions=[
            JabberSession(
                jid=s.jid,
                client=s.client or "unknown",
                ip=s.ip or "",
                connected_seconds=max(int(now - s.connected_at_monotonic), 0),
            )
            for s in sessions
        ],
        truncated=truncated,
    )


@router.get("/federation", response_model=JabberFederation)
def jabber_federation(_: AdminUser, session: SessionDep) -> JabberFederation:
    # Per-remote aggregate: count + last_seen. Direction is derived by checking
    # if both in and out rows exist; a single-direction remote shows its own
    # arrow, bidirectional collapses to "both".
    agg_rows = session.exec(
        select(
            FederationLog.remote_server,
            FederationLog.direction,
            func.count().label("n"),
            func.max(FederationLog.ts).label("last_ts"),
        ).group_by(FederationLog.remote_server, FederationLog.direction)
    ).all()

    per_server: dict[str, dict] = {}
    for server_name, direction, n, last_ts in agg_rows:
        bucket = per_server.setdefault(
            server_name,
            {"count": 0, "last_ts": last_ts, "directions": set()},
        )
        bucket["count"] += n
        bucket["directions"].add(direction)
        if last_ts > bucket["last_ts"]:
            bucket["last_ts"] = last_ts

    now = datetime.now(timezone.utc)
    remotes: list[JabberFederationRemote] = []
    for server_name, bucket in per_server.items():
        dirs = bucket["directions"]
        if dirs == {"in", "out"} or "both" in dirs:
            direction = "both"
        elif dirs == {"in"}:
            direction = "in"
        else:
            direction = "out"
        last_ts: datetime = bucket["last_ts"]
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        remotes.append(
            JabberFederationRemote(
                server=server_name,
                direction=direction,
                message_count=bucket["count"],
                last_active_seconds_ago=max(int((now - last_ts).total_seconds()), 0),
            )
        )
    # Stable order: most recently active first.
    remotes.sort(key=lambda r: r.last_active_seconds_ago)

    recent_rows = session.exec(
        select(FederationLog).order_by(FederationLog.ts.desc()).limit(50)
    ).all()
    recent = [
        JabberFederationMessage(
            ts=row.ts,
            from_jid=row.local_jid if row.direction == "out" else row.remote_jid,
            to_jid=row.remote_jid if row.direction == "out" else row.local_jid,
            preview=row.message_preview,
        )
        for row in recent_rows
    ]

    return JabberFederation(remotes=remotes, recent=recent)
