"""User account management (admin only; FR4.2, Business Rules 5.5)."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import AdminUser, DbSession
from ..models import Role, User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession, _: AdminUser):
    return db.execute(select(User).order_by(User.name)).scalars().all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: DbSession, _: AdminUser):
    email = body.email.lower()
    if db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(name=body.name, email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _active_admin_count(db) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.role == Role.ADMIN, User.is_active.is_(True))
    )


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DbSession, admin: AdminUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    losing_admin = user.role == Role.ADMIN and user.is_active and (
        (body.role is not None and body.role != Role.ADMIN) or body.is_active is False
    )
    if losing_admin and _active_admin_count(db) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "At least one active admin is required")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot deactivate your own account")

    if body.name is not None:
        user.name = body.name.strip()
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user
