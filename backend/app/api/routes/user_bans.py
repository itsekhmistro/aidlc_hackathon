import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import SQLModel, select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.core.social import friendship_between
from app.models.social import UserBan
from app.schemas.social import UserBanPublic

router = APIRouter(prefix="/api/bans", tags=["bans"])


class BanCreate(SQLModel):
    banned_id: uuid.UUID


@router.post("", response_model=UserBanPublic, status_code=status.HTTP_201_CREATED)
async def ban_user(
    current_user: CookieCurrentUser,
    session: SessionDep,
    body: BanCreate,
) -> dict:
    if body.banned_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")

    existing = session.exec(
        select(UserBan).where(
            UserBan.banner_id == current_user.id,
            UserBan.banned_id == body.banned_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already banned")

    # Remove any existing friendship between them
    friendship = friendship_between(session, current_user.id, body.banned_id)
    if friendship:
        session.delete(friendship)

    ban = UserBan(banner_id=current_user.id, banned_id=body.banned_id)
    session.add(ban)
    session.commit()
    session.refresh(ban)

    await presence_manager.send_to_user(
        body.banned_id,
        {"type": "user.banned", "banner_id": str(current_user.id)},
    )

    return UserBanPublic(
        banner_id=ban.banner_id,
        banned_id=ban.banned_id,
        created_at=ban.created_at,
    )


@router.get("", response_model=list[UserBanPublic])
def list_bans(current_user: CookieCurrentUser, session: SessionDep) -> list:
    bans = session.exec(
        select(UserBan).where(UserBan.banner_id == current_user.id)
    ).all()
    return [
        UserBanPublic(banner_id=b.banner_id, banned_id=b.banned_id, created_at=b.created_at)
        for b in bans
    ]


@router.delete("/{banned_id}", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(
    banned_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> None:
    ban = session.exec(
        select(UserBan).where(
            UserBan.banner_id == current_user.id,
            UserBan.banned_id == banned_id,
        )
    ).first()
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")
    if ban.banner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the banner can remove this ban")

    session.delete(ban)
    session.commit()
