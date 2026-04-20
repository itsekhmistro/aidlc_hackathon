from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserPublic, UserUpdate

router = APIRouter()


@router.get("/users/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/users/me", response_model=UserPublic)
def update_user_me(session: SessionDep, user_in: UserUpdate, current_user: CurrentUser) -> User:
    if user_in.email:
        existing = session.exec(select(User).where(User.email == user_in.email)).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="Email already taken")
    user_data = user_in.model_dump(exclude_unset=True)
    if password := user_data.pop("password", None):
        user_data["hashed_password"] = get_password_hash(password)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
