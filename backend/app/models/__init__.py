# Import order matters: tables must exist before FK references
from app.models.user import Presence, PresenceStatus, User, UserSession
from app.models.room import (
    MemberRole,
    Room,
    RoomBan,
    RoomInvitation,
    RoomMember,
    RoomVisibility,
)
from app.models.social import Friendship, FriendshipStatus, UserBan
from app.models.message import Attachment, Message, ReadReceipt
from app.models.federation import FederationLog

__all__ = [
    "User",
    "UserSession",
    "Presence",
    "PresenceStatus",
    "Room",
    "RoomMember",
    "RoomBan",
    "RoomInvitation",
    "RoomVisibility",
    "MemberRole",
    "Friendship",
    "FriendshipStatus",
    "UserBan",
    "Message",
    "Attachment",
    "ReadReceipt",
    "FederationLog",
]
