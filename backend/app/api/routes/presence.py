import uuid

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.presence import presence_manager
from app.models.user import Presence
from app.schemas.social import PresenceBulkRequest, PresenceBulkResponse

router = APIRouter(prefix="/api/presence", tags=["presence"])


@router.post("/bulk", response_model=PresenceBulkResponse)
def bulk_presence(current_user: CookieCurrentUser, session: SessionDep, body: PresenceBulkRequest) -> dict:
    result: dict[str, str] = {}
    for uid in body.user_ids:
        live = presence_manager.compute_status(uid)
        if live != "offline":
            result[str(uid)] = live
        else:
            row = session.get(Presence, uid)
            result[str(uid)] = row.status if row else "offline"
    return {"presences": result}
