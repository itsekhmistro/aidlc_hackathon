import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class FederationLog(SQLModel, table=True):
    """One row per XMPP message that crosses a server boundary.

    Populated by the Prosody webhook (``POST /api/internal/xmpp/event``).
    No FK to ``user``: remote JIDs don't necessarily map to local users, and
    even the local JID may belong to a soft-deleted account — federation
    accounting must survive account tombstones.

    See specs/13-jabber-design.md §1.2.
    """

    __tablename__ = "federation_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    # 'in' or 'out' — stored as text (not enum) to keep webhook payloads trivial
    direction: str = Field(max_length=3)
    local_jid: str = Field(max_length=320)
    remote_jid: str = Field(max_length=320)
    # Denormalised host part of remote_jid, cheap GROUP-BY on the dashboard.
    remote_server: str = Field(max_length=255, index=True)
    # First 140 chars of the message body, or NULL when XMPP_LOG_PREVIEWS=False.
    message_preview: str | None = Field(default=None, max_length=140)
    # Prosody S2S stream id — groups a burst of messages under one connection.
    session_id: str | None = Field(default=None, max_length=64, index=True)
