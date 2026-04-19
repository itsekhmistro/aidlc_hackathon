from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.security import get_password_hash
from app.models.user import User, UserCreate, UserPublic, UsersPublic, UserUpdate

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


@router.post("/users/", response_model=UserPublic)
def create_user(session: SessionDep, user_in: UserCreate) -> User:
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get(
    "/users/",
    response_model=UsersPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> UsersPublic:
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return UsersPublic(data=list(users), count=len(users))
