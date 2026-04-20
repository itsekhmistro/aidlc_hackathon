import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, or_, select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.config import settings
from app.core.presence import presence_manager
from app.models.message import Attachment, Message, ReadReceipt
from app.models.room import MemberRole, Room, RoomBan, RoomInvitation, RoomMember, RoomVisibility
from app.models.user import User
from app.schemas.room import (
    InviteUserRequest,
    RoomBanPublic,
    RoomCreate,
    RoomInvitationPublic,
    RoomMemberPublic,
    RoomPublic,
    RoomUpdate,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


# ─── helpers ─────────────────────────────────────────────────────────────────


def _member_count(session, room_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count()).where(RoomMember.room_id == room_id)
    ).one()


def _to_room_public(session, room: Room) -> RoomPublic:
    return RoomPublic(
        id=room.id,
        name=room.name,
        description=room.description,
        visibility=room.visibility,
        owner_id=room.owner_id,
        is_personal=room.is_personal,
        created_at=room.created_at,
        member_count=_member_count(session, room.id),
    )


def _get_membership(session, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember | None:
    return session.exec(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
    ).first()


def _require_membership(session, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember:
    m = _get_membership(session, room_id, user_id)
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this room")
    return m


def _require_admin(session, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember:
    m = _require_membership(session, room_id, user_id)
    if m.role not in (MemberRole.owner.value, MemberRole.admin.value):
        raise HTTPException(status_code=403, detail="Admin or owner required")
    return m


def _get_room_or_404(session, room_id: uuid.UUID) -> Room:
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def _room_member_ids(session, room_id: uuid.UUID) -> list[uuid.UUID]:
    return session.exec(select(RoomMember.user_id).where(RoomMember.room_id == room_id)).all()


async def _broadcast_room_event(session, room_id: uuid.UUID, event: dict[str, Any]) -> None:
    for uid in _room_member_ids(session, room_id):
        await presence_manager.send_to_user(uid, event)


def _build_member_public(session, member: RoomMember) -> RoomMemberPublic:
    user = session.get(User, member.user_id)
    live = presence_manager.compute_status(member.user_id)
    if live == "offline":
        from app.models.user import Presence
        p = session.get(Presence, member.user_id)
        live = p.status if p else "offline"
    return RoomMemberPublic(
        user_id=member.user_id,
        username=user.username if user else "",
        role=member.role,
        presence_status=live,
        joined_at=member.joined_at,
    )


def _cascade_delete_room(session, room: Room) -> None:
    """Delete all room data (messages, attachments, member records) in FK-safe order."""
    msgs = session.exec(select(Message).where(Message.room_id == room.id)).all()
    for rr in session.exec(select(ReadReceipt).where(ReadReceipt.room_id == room.id)).all():
        session.delete(rr)
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
    session.delete(room)


# ─── routes ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[RoomPublic])
def list_public_rooms(
    current_user: CookieCurrentUser,
    session: SessionDep,
    search: str | None = Query(default=None),
    cursor: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, le=100),
) -> list:
    q = select(Room).where(
        Room.visibility == RoomVisibility.public.value,
        Room.is_personal == False,  # noqa: E712
    )
    if search:
        q = q.where(Room.name.ilike(f"%{search}%"))  # type: ignore[attr-defined]
    if cursor:
        anchor = session.get(Room, cursor)
        if anchor:
            q = q.where(Room.name > anchor.name)
    q = q.order_by(Room.name).limit(limit)
    rooms = session.exec(q).all()
    return [_to_room_public(session, r) for r in rooms]


@router.post("", response_model=RoomPublic, status_code=status.HTTP_201_CREATED)
def create_room(current_user: CookieCurrentUser, session: SessionDep, room_in: RoomCreate) -> dict:
    if session.exec(select(Room).where(Room.name == room_in.name)).first():
        raise HTTPException(status_code=422, detail="Room name already taken")

    room = Room(
        name=room_in.name,
        description=room_in.description,
        visibility=room_in.visibility.value,
        owner_id=current_user.id,
        is_personal=False,
    )
    session.add(room)
    session.flush()

    member = RoomMember(room_id=room.id, user_id=current_user.id, role=MemberRole.owner.value)
    session.add(member)
    session.commit()
    session.refresh(room)
    return _to_room_public(session, room)


@router.get("/invitations/mine", response_model=list[RoomInvitationPublic])
def my_invitations(current_user: CookieCurrentUser, session: SessionDep) -> list:
    rows = session.exec(
        select(RoomInvitation).where(
            RoomInvitation.invited_user_id == current_user.id,
            RoomInvitation.accepted_at.is_(None),  # type: ignore[attr-defined]
        )
    ).all()
    return list(rows)


@router.post("/invitations/{invitation_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invitation(invitation_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    inv = session.exec(
        select(RoomInvitation).where(
            RoomInvitation.id == invitation_id,
            RoomInvitation.invited_user_id == current_user.id,
            RoomInvitation.accepted_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")

    # Check not already banned
    ban = session.exec(
        select(RoomBan).where(RoomBan.room_id == inv.room_id, RoomBan.user_id == current_user.id)
    ).first()
    if ban:
        raise HTTPException(status_code=403, detail="You are banned from this room")

    # Add membership if not already present
    if not _get_membership(session, inv.room_id, current_user.id):
        session.add(RoomMember(room_id=inv.room_id, user_id=current_user.id, role=MemberRole.member.value))

    inv.accepted_at = datetime.now(timezone.utc)
    session.add(inv)
    session.commit()

    member = _get_membership(session, inv.room_id, current_user.id)
    await _broadcast_room_event(session, inv.room_id, {
        "type": "room.member_joined",
        "room_id": str(inv.room_id),
        "user": _build_member_public(session, member).model_dump(mode="json"),
    })


@router.get("/mine", response_model=list[RoomPublic])
async def get_my_rooms(current_user: CookieCurrentUser, session: SessionDep) -> list:
    members = session.exec(select(RoomMember).where(RoomMember.user_id == current_user.id)).all()
    room_ids = [m.room_id for m in members]
    if not room_ids:
        return []
    rooms = session.exec(select(Room).where(Room.id.in_(room_ids))).all()  # type: ignore[attr-defined]
    return [_to_room_public(session, r) for r in rooms]


@router.get("/{room_id}", response_model=RoomPublic)
def get_room(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> dict:
    room = _get_room_or_404(session, room_id)
    if room.visibility == RoomVisibility.private.value:
        _require_membership(session, room_id, current_user.id)
    return _to_room_public(session, room)


@router.patch("/{room_id}", response_model=RoomPublic)
async def update_room(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep, room_in: RoomUpdate) -> dict:
    room = _get_room_or_404(session, room_id)
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Owner only")

    changes: dict[str, Any] = {}
    if room_in.name is not None:
        if session.exec(select(Room).where(Room.name == room_in.name, Room.id != room_id)).first():
            raise HTTPException(status_code=422, detail="Room name already taken")
        room.name = room_in.name
        changes["name"] = room_in.name
    if room_in.description is not None:
        room.description = room_in.description
        changes["description"] = room_in.description
    if room_in.visibility is not None:
        room.visibility = room_in.visibility.value
        changes["visibility"] = room_in.visibility.value

    session.add(room)
    session.commit()
    session.refresh(room)

    if changes:
        await _broadcast_room_event(session, room_id, {
            "type": "room.updated",
            "room_id": str(room_id),
            "changes": changes,
        })
    return _to_room_public(session, room)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    room = _get_room_or_404(session, room_id)
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Owner only")

    member_ids = _room_member_ids(session, room_id)
    _cascade_delete_room(session, room)
    session.commit()

    # Notify then clean up uploads
    for uid in member_ids:
        await presence_manager.send_to_user(uid, {"type": "room.deleted", "room_id": str(room_id)})
    shutil.rmtree(os.path.join(settings.UPLOAD_DIR, str(room_id)), ignore_errors=True)


@router.post("/{room_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_room(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    room = _get_room_or_404(session, room_id)

    if room.visibility != RoomVisibility.public.value:
        raise HTTPException(status_code=403, detail="Room is private — join via invitation")

    ban = session.exec(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == current_user.id)
    ).first()
    if ban:
        raise HTTPException(status_code=403, detail="You are banned from this room")

    if _get_membership(session, room_id, current_user.id):
        return  # already a member — idempotent

    member = RoomMember(room_id=room_id, user_id=current_user.id, role=MemberRole.member.value)
    session.add(member)
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.member_joined",
        "room_id": str(room_id),
        "user": _build_member_public(session, member).model_dump(mode="json"),
    })


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    room = _get_room_or_404(session, room_id)
    if room.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot leave — delete the room instead")

    member = _get_membership(session, room_id, current_user.id)
    if not member:
        return  # not a member — idempotent

    session.delete(member)
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.member_left",
        "room_id": str(room_id),
        "user_id": str(current_user.id),
    })


@router.get("/{room_id}/members", response_model=list[RoomMemberPublic])
def list_members(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> list:
    _get_room_or_404(session, room_id)
    _require_membership(session, room_id, current_user.id)
    members = session.exec(select(RoomMember).where(RoomMember.room_id == room_id)).all()
    return [_build_member_public(session, m) for m in members]


@router.post("/{room_id}/members/{user_id}/admin", status_code=status.HTTP_204_NO_CONTENT)
async def grant_admin(room_id: uuid.UUID, user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    room = _get_room_or_404(session, room_id)
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Owner only")

    target = _get_membership(session, room_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User is not a member")
    if target.role == MemberRole.owner.value:
        raise HTTPException(status_code=400, detail="Cannot modify owner role")

    target.role = MemberRole.admin.value
    session.add(target)
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.admin_granted",
        "room_id": str(room_id),
        "user_id": str(user_id),
    })


@router.delete("/{room_id}/members/{user_id}/admin", status_code=status.HTTP_204_NO_CONTENT)
async def remove_admin(room_id: uuid.UUID, user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    room = _get_room_or_404(session, room_id)
    caller = _require_admin(session, room_id, current_user.id)

    target = _get_membership(session, room_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User is not a member")
    if target.role == MemberRole.owner.value:
        raise HTTPException(status_code=400, detail="Cannot demote the owner")
    # Admin can only demote others; owner can demote any admin
    if caller.role == MemberRole.admin.value and target.role == MemberRole.admin.value and user_id == current_user.id:
        raise HTTPException(status_code=403, detail="Cannot demote yourself")

    target.role = MemberRole.member.value
    session.add(target)
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.admin_removed",
        "room_id": str(room_id),
        "user_id": str(user_id),
    })


@router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def ban_member(room_id: uuid.UUID, user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    _get_room_or_404(session, room_id)
    _require_admin(session, room_id, current_user.id)

    target = _get_membership(session, room_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User is not a member")
    if target.role == MemberRole.owner.value:
        raise HTTPException(status_code=400, detail="Cannot ban the owner")

    # Remove membership
    session.delete(target)

    # Add ban
    existing_ban = session.exec(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == user_id)
    ).first()
    if not existing_ban:
        session.add(RoomBan(room_id=room_id, user_id=user_id, banned_by_id=current_user.id))
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.member_banned",
        "room_id": str(room_id),
        "user_id": str(user_id),
        "banned_by": str(current_user.id),
    })


@router.get("/{room_id}/bans", response_model=list[RoomBanPublic])
def list_bans(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> list:
    _get_room_or_404(session, room_id)
    _require_admin(session, room_id, current_user.id)

    bans = session.exec(select(RoomBan).where(RoomBan.room_id == room_id)).all()
    result = []
    for ban in bans:
        banned_user = session.get(User, ban.user_id)
        banner = session.get(User, ban.banned_by_id)
        result.append(RoomBanPublic(
            user_id=ban.user_id,
            username=banned_user.username if banned_user else "",
            banned_by_id=ban.banned_by_id,
            banned_by_username=banner.username if banner else "",
            banned_at=ban.banned_at,
        ))
    return result


@router.delete("/{room_id}/bans/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unban_member(room_id: uuid.UUID, user_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    _get_room_or_404(session, room_id)
    _require_admin(session, room_id, current_user.id)

    ban = session.exec(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == user_id)
    ).first()
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    session.delete(ban)
    session.commit()

    await _broadcast_room_event(session, room_id, {
        "type": "room.member_unbanned",
        "room_id": str(room_id),
        "user_id": str(user_id),
    })


@router.post("/{room_id}/invitations", response_model=RoomInvitationPublic, status_code=status.HTTP_201_CREATED)
async def invite_user(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep, body: InviteUserRequest) -> dict:
    room = _get_room_or_404(session, room_id)
    _require_membership(session, room_id, current_user.id)

    target_user = session.exec(
        select(User).where(User.username == body.username, User.deleted_at.is_(None))  # type: ignore[attr-defined]
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if _get_membership(session, room_id, target_user.id):
        raise HTTPException(status_code=400, detail="User is already a member")

    ban = session.exec(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == target_user.id)
    ).first()
    if ban:
        raise HTTPException(status_code=400, detail="User is banned from this room")

    existing = session.exec(
        select(RoomInvitation).where(
            RoomInvitation.room_id == room_id,
            RoomInvitation.invited_user_id == target_user.id,
            RoomInvitation.accepted_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if existing:
        return existing

    inv = RoomInvitation(
        room_id=room_id,
        invited_by_id=current_user.id,
        invited_user_id=target_user.id,
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)

    await presence_manager.send_to_user(target_user.id, {
        "type": "room.invitation",
        "room_id": str(room_id),
        "room_name": room.name,
        "invited_by": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "created_at": current_user.created_at.isoformat(),
        },
    })
    return inv


@router.get("/{room_id}/invitations", response_model=list[RoomInvitationPublic])
def list_invitations(room_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> list:
    _get_room_or_404(session, room_id)
    _require_admin(session, room_id, current_user.id)

    rows = session.exec(
        select(RoomInvitation).where(
            RoomInvitation.room_id == room_id,
            RoomInvitation.accepted_at.is_(None),  # type: ignore[attr-defined]
        )
    ).all()
    return list(rows)
