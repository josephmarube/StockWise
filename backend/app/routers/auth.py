"""FR4.1 User Login."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import User
from ..schemas import LoginRequest, MeOut, TokenResponse
from ..security import create_access_token, dummy_verify, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid email or password"


def issue_token(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, expires_in=expires_in, user=MeOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession):
    user = db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    ).scalar_one_or_none()

    if user is None:
        dummy_verify()  # keep response time similar for unknown emails
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    if (
        not verify_password(body.password, user.password_hash)
        or not user.is_active
        or not user.business.is_active
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    return issue_token(user)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return user
