import uuid

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.social import Friendship, UserBan


def friendship_between(session: Session, a: uuid.UUID, b: uuid.UUID) -> Friendship | None:
    return session.exec(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    ).first()


def ban_between(session: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    return (
        session.exec(
            select(UserBan).where(
                or_(
                    and_(UserBan.banner_id == a, UserBan.banned_id == b),
                    and_(UserBan.banner_id == b, UserBan.banned_id == a),
                )
            )
        ).first()
        is not None
    )
