"""Response + webhook request shapes for the XMPP/Jabber bridge (TASK-13).

Contract defined in specs/13-jabber-design.md §2.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import Field
from sqlmodel import SQLModel


# ── GET /api/admin/jabber/status ──────────────────────────────────────────────


class JabberSession(SQLModel):
    jid: str
    client: str
    ip: str
    connected_seconds: int


class JabberStatus(SQLModel):
    server_host: str
    uptime_seconds: int
    connected_clients: int
    s2s_links_active: int
    sessions: list[JabberSession] = Field(default_factory=list)
    truncated: bool = False


# ── GET /api/admin/jabber/federation ──────────────────────────────────────────


class JabberFederationRemote(SQLModel):
    server: str
    direction: Literal["in", "out", "both"]
    message_count: int
    last_active_seconds_ago: int


class JabberFederationMessage(SQLModel):
    ts: datetime
    from_jid: str
    to_jid: str
    preview: str | None = None


class JabberFederation(SQLModel):
    remotes: list[JabberFederationRemote] = Field(default_factory=list)
    recent: list[JabberFederationMessage] = Field(default_factory=list)


# ── POST /api/internal/xmpp/event (Prosody webhook) ───────────────────────────


class XmppFederationEvent(SQLModel):
    """Prosody pushes one of these per message that crosses a server boundary."""

    type: Literal["federation.message"]
    ts: datetime
    direction: Literal["in", "out"]
    local_jid: str
    remote_jid: str
    remote_server: str
    message_preview: str | None = None
    session_id: str | None = None


class XmppSessionEvent(SQLModel):
    """Prosody pushes one of these on a c2s login/logout."""

    type: Literal["session.client"]
    ts: datetime
    event: Literal["login", "logout"]
    jid: str
    client: str | None = None
    ip: str | None = None
    session_id: str | None = None


# Discriminated union used by the webhook handler to route by ``type``.
XmppEventEnvelope = Annotated[
    Union[XmppFederationEvent, XmppSessionEvent],
    Field(discriminator="type"),
]
